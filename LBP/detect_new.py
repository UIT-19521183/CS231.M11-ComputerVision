def sliding_window(image, window_size, step_size):
    for y in range(0, image.shape[0], step_size[1]):
        for x in range(0, image.shape[1], step_size[0]):
            yield (x, y, image[y: y + window_size[1], x: x + window_size[0]])

path = 'Path to image'
import numpy as np 
import cv2,joblib
from imutils.object_detection import non_max_suppression
import imutils
from skimage.feature import hog
from skimage import color
from skimage.transform import pyramid_gaussian
from google.colab.patches import cv2_imshow

image = cv2.imread(path)
image = cv2.resize(image,(400,256))
size = (64,128)
step_size = (15,15)
downscale = 1.25
#List to store the detections
detections = []
#The current scale of the image 
scale = 0.1
model = joblib.load('pedestrian_final_hard_HL.pkl')
prediction = []
for im_scaled in pyramid_gaussian(image, downscale = downscale):
    #The list contains detections at the current scale
    if im_scaled.shape[0] < size[1] or im_scaled.shape[1] < size[0]:
        break
    for (x, y, window) in sliding_window(im_scaled, size, step_size):
        if window.shape[0] != size[1] or window.shape[1] != size[0]:
            continue
        window = color.rgb2gray(window)
            
        fd=calc_lbp(window)
        fd1 = hog(cv2.resize (window, (64, 128)), orientations = 9, pixels_per_cell=(8,8), cells_per_block=(2,2))
        fd_new = np.append(fd, fd1)
        fd_new = fd_new.reshape(1, -1)
        pred = model.predict(fd_new)
        if pred == 1:
            if model.decision_function(fd_new) >= 0.5:
                detections.append((int(x * (downscale**scale)), int(y * (downscale**scale)), model.decision_function(fd_new), 
                int(size[0] * (downscale**scale)),
                int(size[1] * (downscale**scale))))
 
    scale += 1
print (detections)
clone = image.copy()
rects = np.array([[x, y, x + w, y + h] for (x, y, _, w, h) in detections])
sc = [score[0] for (x, y, score, w, h) in detections]
print ("sc: ", sc)
sc = np.array(sc)
pick = non_max_suppression(rects, probs = sc, overlapThresh = 0.1)
#pick = nms(rects, 0.4)
for(x1, y1, x2, y2) in pick:
    cv2.rectangle(clone, (x1, y1), (x2, y2), (0, 0, 255), 2)
    cv2.putText(clone,'Person',(x1-2,y1-2),1,0.75,(121,12,34),1)
    print (x1, y1, x2, y2)
cv2_imshow(clone)
cv2.waitKey(0)
cv2.destroyAllWindows()