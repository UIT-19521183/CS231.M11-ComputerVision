import os
import cv2
import numpy as np
import pandas as pd
from collections import deque
import joblib
from HOG import *
from skimage.feature import hog
import argparse
import itertools

"""
parser = argparse.ArgumentParser(description='Parse Detection Directory')
parser.add_argument('-i', '--input', help='Path to directory containing images for detection', required=True)
parser.add_argument('-o', '--output', help='Path to directory for result images', required=True)
parser.add_argument('-w', '--weight', help="Path to file containing model's weights", required=True)
parser.add_argument('-c', '--csv', help='Path to directory for result csv file', action="store_true")

args = parser.parse_args()
detect_dir = args.i
result_dir = args.o
weight_file = args.w
"""

weight_file='SVM_rbf1.pkl'
detect_dir='detect_dir'
result_dir='result_dir'
scaler= joblib.load('scaler.save')

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
    max_confidence=detects[0][-1]
    for i in range(len(detects)):
        if(max_confidence<detects[i][-1]):
            max_confidence=detects[i][-1]
        if detects[i][-1] < 0.999:
            detects = detects[:i]
            break
    print("confidence>0.999999:",len(detects))
    print("max confidence:",max_confidence)

    # Bỏ đi các bounding boxes chồng lên nhau có iou > 0.6
    keeps = deque([])
    while detects != []:
        #Lấy rectangle đầu tiên để xét
        temp=detects[0]
        #Bỏ nó ra khỏi detects
        detects = detects[1:]
        i = 0
        while i < len(detects):
            if iou(detects[i], temp) > 0.2:
                #Nếu confidence lớn hơn thì lấy rectangle này thay vì rectangle cũ
                if(detects[i][-1]>temp[-1]):
                    temp=detects[i]
                #Bỏ rectangle đã xét có IoU giao nhau khá lớn với rectangle temp
                detects = detects[:i] + detects[i + 1:]
                i -= 1
            i += 1
        # Cuối cùng thêm rectangle có confidence max trong các rectangle có IoU với nhau lớn
        keeps.append(temp)
    print("Vẫn còn:",len(keeps))
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

cell_size = (8,8)
block_size = (2, 2)

window_size = (64, 128)  # kích thước cửa số và kích thước của mỗi bước trượt cửa số (w x h)
window_stride = cell_size
if window_stride[0] < 8:
    window_stride = (8, 8)

image_files = deque([])
rois = deque([])
confidence_scores = deque([])


def main(image_files,rois,confidence_scores):
    for image in os.listdir(detect_dir):
        img = cv2.imread(os.path.join(detect_dir, image))
        print(img.shape)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_img = cv2.GaussianBlur(gray_img, (5, 5), 0)

        rects = deque([])
        result = img.copy()

        #scales = np.arange(1,2,1)  # Tạo pyramid chứa các ảnh resize với tỉ lệ 0.5, 1 (ảnh gốc), 1.5
        scales=np.array([0.4,0.7,0.9,1.1,1.25])
        print(scales)
        scaled_grays = pyramid(gray_img, cell_size, scales)
        for img,dem in zip(scaled_grays,scales):
            #trượt slide_window
            x=0
            y=0
            h_img,w_img=img.shape[0],img.shape[1]
            while y+window_size[1]<h_img:
                while x+window_size[0]<w_img:
                    window=img[y:y+window_size[1],x:x+window_size[0]]
                    #extract feature
                    feature=hog(window,pixels_per_cell=cell_size, cells_per_block=block_size, orientations=9)
                    feature=np.array([feature])
                    feature=scaler.transform(feature)
                    #Dự đoán xem window có chứa người hay không
                    pred=clf.predict(feature)
                    if pred[0]:
                        #confidence=clf.decision_function(feature)
                        confidence=clf.predict_proba(feature)
                        confidence=max(confidence[-1])
                        rects.append([int(x/dem),int(y/dem),int(window_size[0]/dem),int(window_size[1]/dem),confidence])

                    x+=cell_size[0]
                x=0
                y+=cell_size[1]

        print(len(rects))
        keeps = nms(rects)
        print(len(keeps))
        for k in keeps:
            cv2.rectangle(result, (k[0], k[1]), (k[0] + k[2], k[1] + k[3]), (0, 0, 255), 2)
            image_files.append(image)
            #x=list(k[:-1])
            #RectoString=",".join(x)
            #rois.append(RectoString)
            rois.append(k[:-1])
            confidence_scores.append(k[-1])

        # Lưu ảnh kết quả
        cv2.imwrite(os.path.join(result_dir, image), result)
    from numpy import savetxt
    #image_files = np.array(image_files)
    #rois = np.array(rois)
    #confidence_scores = np.array(confidence_scores)
    # data=np.concatenate((image_files,rois,confidence_scores),axis=1)
    # print(data.shape)
    if True:  # Lưu file csv
        df = pd.DataFrame({
            'image file': image_files,
            'roi': rois,
            'confidence': confidence_scores})
        df.to_csv(os.path.join(result_dir, 'result.csv'), index=False)

    # savetxt(os.path.join(result_dir,'result.csv'), data, delimiter=',')






import cProfile
if __name__ == "__main__":
    #cProfile.run("main()")
    main(image_files,rois,confidence_scores)