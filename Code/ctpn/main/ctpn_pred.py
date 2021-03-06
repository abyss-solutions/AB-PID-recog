# coding=utf-8
import os
import shutil
import sys
import time
import pytesseract
import cv2
import numpy as np
import tensorflow as tf

from ctpn.nets import model_train as model
from ctpn.utils.rpn_msr.proposal_layer import proposal_layer
from ctpn.utils.text_connector.detectors import TextDetector
from preprocess.preprocess import get_images, resize_image
from utils.utils import  txtremove

def ctpn_pred(input_path, output_path,textloc_output_path, checkpoint_path,gpu):
    print("========== detect text using ctpn ==============")
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path)
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    tf.reset_default_graph()
    with tf.get_default_graph().as_default():
        
        input_image = tf.placeholder(tf.float32, shape=[None, None, None, 3], name='input_image')
        input_im_info = tf.placeholder(tf.float32, shape=[None, 3], name='input_im_info')

        global_step = tf.get_variable('global_step', [], initializer=tf.constant_initializer(0), trainable=False)

        bbox_pred, cls_pred, cls_prob = model.model(input_image)

        variable_averages = tf.train.ExponentialMovingAverage(0.997, global_step)
        saver = tf.train.Saver(variable_averages.variables_to_restore())

        with tf.Session(config=tf.ConfigProto(allow_soft_placement=True)) as sess:
            ckpt_state = tf.train.get_checkpoint_state(checkpoint_path)
            model_path = os.path.join(checkpoint_path, os.path.basename(ckpt_state.model_checkpoint_path))
            saver.restore(sess, model_path)

            im_fn_list = get_images(input_path)
            for im_fn in im_fn_list:
                print('===============')
                print(im_fn)

                #remove existing detected component from text
                txtfileloc = os.path.join (textloc_output_path, os.path.splitext(os.path.basename(im_fn))[0]) + "_loc.txt"
                if os.path.isfile(txtfileloc):
                    f =  open(txtfileloc, 'r+')
                    textlines = txtremove(f,['ORIG','ROT'])
                    f.seek(0)
                    f.write(textlines)
                    f.truncate()
                    f.close()   

                start = time.time()
                try:
                    img_raw = cv2.imread(im_fn)
                except:
                    print("Error reading image {}!".format(im_fn))
                    continue
                # image used to draw bounding box
                H, W, _ = img_raw.shape
                img_blank =  np.ones(shape=[H, W], dtype=np.uint8)*255
                img_draw = img_raw.copy()

                img, (rh, rw) = resize_image(img_raw)
                h, w, c = img.shape
                res = []
                for ifrot in ['ORIG','ROT']:
                    im = img.copy()

                    if ifrot == 'ROT':
                        im = cv2.transpose(im)
                        im = cv2.flip(im,1)
                        bbox_color = (255,0,0)
                        im_info = np.array([w, h, c]).reshape([1, 3])
                    else: 
                        bbox_color = (0,255,0)
                        im_info = np.array([h, w, c]).reshape([1, 3])
                    bbox_pred_val, cls_prob_val = sess.run([bbox_pred, cls_prob],
                                                           feed_dict={input_image: [im],
                                                                      input_im_info: im_info})
    
                    textsegs, _ = proposal_layer(cls_prob_val, bbox_pred_val, im_info)
                    scores = textsegs[:, 0]
                    textsegs = textsegs[:, 1:5]
                    
                    textdetector = TextDetector(DETECT_MODE='H')
                    boxes = textdetector.detect(textsegs, scores[:, np.newaxis], im.shape[:2])
                    boxes = np.array(boxes, dtype=np.int)
                    print("Find number of text:",len(boxes))
                    cost_time = (time.time() - start)
                    print("cost time: {:.2f}s".format(cost_time))
                    fx=1.0 / rw
                    fy=1.0 / rh

                    for i, box in enumerate(boxes):
                        if ifrot == 'ROT':
                            box = np.array([box[3],h-box[2],box[5],h-box[4],box[7],h-box[6],box[1],h-box[0],box[8]])
                            
                        #resize the images
                        box[:8:2] = (box[:8:2]*fx).astype(np.int32)
                        box[1::2] = (box[1::2]*fy).astype(np.int32)
                        loc = [int(i) for i in box[0:-1]]
                       
                        # crop image with rectangle box and save
                        x0,y0,w0,h0 = cv2.boundingRect(np.array(loc[:8]).astype(np.int32).reshape((-1, 2)))
                        img_crop = img_blank[y0:y0+h0,x0:x0+w0].copy()
                        hc, wc = img_crop.shape[:2]
                        countzero = hc*wc - cv2.countNonZero(img_crop)

                        if countzero *1.0 / (hc*wc) <= 0.2:
                            # if there is minimum overlap with previous bounding box
                            
                            cv2.drawContours(img_blank, [np.array(loc).reshape((-1,1,2))], 0, (0), thickness = -1, lineType=8)
                            cv2.polylines(img_draw, [box[:8].astype(np.int32).reshape((-1, 1, 2))], True, color=bbox_color, thickness=2)
                            # crop image with rectangle box and save
                            x0,y0,w0,h0 = cv2.boundingRect(box[:8].astype(np.int32).reshape((-1, 2)))
                            img_crop = img_raw[y0:y0+h0,x0:x0+w0].copy()
                            txtrecog = txt_recog(img_crop)
                            res.append([ifrot]+loc+[txtrecog]) 
                            cv2.imwrite(os.path.join(output_path, os.path.splitext(os.path.basename(im_fn))[0])+"_"+ifrot+"_"+str(format(i, "04"))+".jpg", img_crop) 
                            cv2.putText(img_draw, str(i), (box[0],box[1]), cv2.FONT_HERSHEY_SIMPLEX ,1.0, bbox_color, 2, cv2.LINE_AA) 
                cv2.imwrite(os.path.join(output_path, os.path.splitext(os.path.basename(im_fn))[0])+"_"+ifrot+".jpg", img_draw) 
                
                with open(txtfileloc, "a") as f:
                    for i, ir in enumerate(res):
                        line = "\t".join(str(ir[k]) for k in range(10))
                        line += "\n"
                        print(line)
                        f.writelines(line)
                    f.close()


def txt_recog(cropimg):
    """
    text recognition
    """
    retval, threshold = cv2.threshold(cropimg,127,255,cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(threshold,lang='eng', config='--psm 6 --oem 2 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-/\\"')
    return text