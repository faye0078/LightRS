array_of_img = []
try:
    import Image
    import ImageDraw
except:
    from PIL import Image
    from PIL import ImageDraw
import cv2
import glob
import numpy as np
import os
import sys
def get_gid_labels():
    return np.array([
        [255,0,0],    #buildup
        [0,255,0],   #farmland
        [0,255,255],  #forest
        [255,255,0],  #meadow
        [0,0,255] ])  #water
def get_index(rgb):
    if (rgb == [255, 0, 0]).all():
        return 1
    elif (rgb == [0, 255, 0]).all():
        return 2
    elif (rgb == [0, 0, 255]).all():
        return 3
    elif (rgb == [0, 255, 255]).all():
        return 4
    elif (rgb == [0, 0, 0]).all():
        return 0
    else:
        print("other RGB")
        return 0

def getGray(filepath):
    gray = []
    for filename0 in os.listdir(filepath):
        imgs = glob.glob('{}*.png'.format(filepath + "/" + filename0 + "/"))
        for filename in imgs:
            # print(filename) #just for test
            # img is used to store the image data
            img = Image.open(filename)
            gray_img = img.convert("L")
            img = np.array(gray_img)
            for i in range(img.shape[0]):
                for j in range(img.shape[1]):
                    test = img[i][j]
                    choice = True
                    for k in range(len(gray)):
                        if gray[k] == test:
                            choice = False
                    if choice:
                        gray.append(test)
                    print(gray)
        print(gray)

def getRGB(filepath):
    gray = []
    for filename0 in os.listdir(filepath):
        imgs = glob.glob('{}*.tif'.format(filepath + "/" + filename0 + "/"))
        for filename in imgs:
            # print(filename) #just for test
            # img is used to store the image data
            img = Image.open(filename)
            img = np.array(img)
            for i in range(img.shape[0]):
                for j in range(img.shape[1]):
                    test = img[i][j]
                    choice = True
                    for k in range(len(gray)):
                        if (gray[k] == test).all():
                            choice = False
                    if choice:
                        gray.append(test)
                    print(gray)
        print(gray)

def tif2label(filepath):
    for filename0 in os.listdir(filepath):
        imgs = glob.glob('{}*.tif'.format(filepath + "/" + filename0 + "/"))
        for filename in imgs:
        # print(filename) #just for test
        # img is used to store the image data
            img = Image.open(filename)
            # gray_img = img.convert("L")
        #             # gray_img = np.array(gray_img)
        #     img = np.array(img)
            img = np.uint8(img)
            # label_mask = np.zeros((mask.shape[0], mask.shape[1]), dtype=np.int16)
            label_mask = 255 * np.ones((img.shape[0], img.shape[1]), dtype=np.uint8)
            for ii, label in enumerate(get_gid_labels()):
                label_mask[np.where(np.all(img == label, axis=-1))[:2]] = ii
            label_mask = np.uint8(label_mask)
            # for i in range(img.shape[0]):
            #      for j in range(img.shape[1]):
            #             gray_img[i][j] = get_index(img[i][j])
            folder = os.path.exists("E:/wangyu_file/label/" + filename0)
            # ????????????????????????????????????????????????????????????
            if not folder:  # ???????????????????????????????????????????????????????????????
                os.makedirs("E:/wangyu_file/label/" + filename0)
            filename = filename.replace(".tif", ".png")
            filename = "E:/wangyu_file/label/" + filename0 + "/" + filename.split("\\")[1]
            result = Image.fromarray(label_mask, 'P')
            result.save(filename)

img_dir = "E:/wangyu_file/rs_Nas/src/data/datasets/VOCdevkit/512/train/gray_label"
# img_dir = "E:/wangyu_file/label"
# tif2label(img_dir)
getGray(img_dir)