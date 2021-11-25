import os
import cv2
import numpy as np
import pandas as pd
from collections import deque
import joblib
from HOG import *
import argparse

parser = argparse.ArgumentParser(description='Parse Detection Directory')
parser.add_argument('-i', '--input', help='Path to directory containing images for detection', required=True)
parser.add_argument('-o', '--output', help='Path to directory for result images', required=True)
parser.add_argument('-w', '--weight', help="Path to file containing model's weights", required=True)
parser.add_argument('-c', '--csv', help='Path to directory for result csv file', action="store_true")

args = parser.parse_args()
detect_dir = args.i
result_dir = args.o
weight_file = args.w


# Hàm tính iou
def iou(box1, box2):
    x1_left, y1_top = box1[0], box1[1]
    x1_right, y1_bottom = x1_left + box1[2], y1_top + box1[3]
    x2_left, y2_top = box2[0], box2[1]
    x2_right, y2_bottom = x2_left + box2[2], y2_top + box2[3]

    w_overlap = max(0, min(x1_right, x2_right) - max(x1_left, x2_left))
    h_overlap = max(0, min(y1_bottom, y2_bottom) - max(y1_top, y2_top))

    overlap_area = w_overlap * h_overlap
    union_area = box1[2] * box1[3] + box2[2] * box2[3] - overlap_area

    return overlap_area / float(union_area)


# Non-max suppression
def nms(rects):
    if not rects:
        return []

    # Sắp xếp các detection theo confidence và bỏ những detection có confidence < 0.5
    detects = sorted(rects, key=lambda rect: rect[-1], reverse=True)  # sắp theo confidence giảm dần
    for i in range(len(detects)):
        if detects[i][-1] < 0.3:
            detects = detects[:i]
            break

    # Bỏ đi các bounding boxes chồng lên nhau có iou > 0.6
    keeps = deque([])
    while detects != []:
        keeps.append(detects[0])
        detects = detects[1:]
        i = 0
        while i < len(detects):
            if iou(detects[i], keeps[-1]) > 0.6:
                detects = detects[:i] + detects[i + 1:]
                i -= 1
            i += 1

    return keeps


# Tạo pyramid chứa các ảnh được resize với các tỉ lệ khác nhau
def pyramid(img, cell_size, scales):
    scaled_imgs = []
    width, height = img.shape[1], img.shape[0]
    for scale in scales:
        resized = resize_closest(img, cell_size, scale)
        scaled_imgs.append(resized)
    return scaled_imgs


cells = {
    70308: (2, 2),
    16740: (4, 4),
    3780: (8, 8),
    756: (16, 16),
    108: (32, 32)
}

clf = joblib.load(weight_file)

cell_size = cells[len(clf.coef_[0])]
block_size = (2, 2)

window_size = (64, 128)  # kích thước cửa số và kích thước của mỗi bước trượt cửa số (w x h)
window_stride = cell_size
if window_stride[0] < 8:
    window_stride = (8, 8)

image_files = deque([])
rois = deque([])
confidence_scores = deque([])

for image in os.listdir(detect_dir):
    img = cv2.imread(os.path.join(detect_dir, image))
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_img = cv2.GaussianBlur(gray_img, (5, 5), 0)

    rects = deque([])
    result = img.copy()

    scales = np.arange(0.1, 5.1, 0.1)  # Tạo pyramid chứa các ảnh resize với tỉ lệ 0.5, 1 (ảnh gốc), 1.5
    scaled_grays = pyramid(gray_img, cell_size, scales)
    for img in scaled_grays:
        #trượt slide_window
        x=0
        y=0
        h_img,w_img=img.shape[0],img.shape[1]
        while x+window_size[0]<w_img and y+window_size[1]<h_img:
            window=img[y:y+window_stride[1],x:x+window_stride[0]]
            #extract feature
            feature=extract_hog_feature_vector(window,cell_size,block_size)
            #Dự đoán xem window có chứa người hay không
            pred=clf.predict([feature])
            if pred[0]:
                confidence=clf.decision_function([feature])
                rects.append([x,y,x+window_size[0],y+window_size[1],confidence])



    keeps = nms(rects)
    for k in keeps:
        cv2.rectangle(result, (k[0], k[1]), (k[0] + k[2], k[1] + k[3]), (0, 0, 255), 2)

        if args.c:  # Viết vào file csv
            image_files.append(image)
            rois.append(k[:-1])
            confidence_scores.append(k[-1][0])
    #cv2.imshow(result)

    # Lưu ảnh kết quả
    cv2.imwrite(os.path.join(result_dir, image), result)

if args.c:  # Lưu file csv
    df = pd.DataFrame({
        'image file': image_files,
        'roi': rois,
        'confidence': confidence_scores})
    df.head()
    df.to_csv(os.path.join(result_dir, 'result.csv'), index=False)