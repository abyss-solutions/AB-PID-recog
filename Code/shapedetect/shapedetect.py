
import cv2
import numpy as np
from preprocess.preprocess import get_images
import os
import shutil
from skimage.transform import probabilistic_hough_line
from utils.utils import txtremove, scale_contour

def thinning (img):
    img1 = img.copy()
 
    # Structuring Element
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))
    # Create an empty output image to hold values
    thin = np.zeros(img.shape,dtype='uint8')
 
    # Loop until erosion leads to an empty set
    while (cv2.countNonZero(img1)!=0):
        # Erosion
        erode = cv2.erode(img1,kernel)
        # Opening on eroded image
        opening = cv2.morphologyEx(erode,cv2.MORPH_OPEN,kernel)
        # Subtract these two
        subset = erode - opening
        # Union of all previous sets
        thin = cv2.bitwise_or(subset,thin)
        # Set the eroded image for next iteration
        img1 = erode.copy()
    return thin

"""
def dilatation(image, dilatation_size, val_type):
    if val_type == 0:
        dilatation_type = cv2.MORPH_RECT
    elif val_type == 1:
        dilatation_type = cv2.MORPH_CROSS
    elif val_type == 2:
        dilatation_type = cv2.MORPH_ELLIPSE
    element = cv2.getStructuringElement(dilatation_type, (dilatation_size, dilatation_size))
    dilatation_dst = cv2.dilate(image, element,iterations = 1)
    return dilatation_dst

def erosion(image,erosion_size, val_type):
    if val_type == 0:
        erosion_type = cv2.MORPH_RECT
    elif val_type == 1:
        erosion_type = cv2.MORPH_CROSS
    elif val_type == 2:
        erosion_type = cv2.MORPH_ELLIPSE
    element = cv2.getStructuringElement(erosion_type, (erosion_size , erosion_size))
    erosion_dst = cv2.erode(image, element,iterations = 1)
    return erosion_dst
"""



def inoutlet_detect(input_path,output_path, ifmask, maskloc_output_path):
    """
    Identify the inlet and outlet arrow.
    ifmast ==  True, the area will be masked in output drawing
    """
    print("========== detect inlet and outlet ==============")
    epsilon = 0.02
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path)
    img_fn_list = get_images(input_path)
    for img_fn in img_fn_list:
        print('===============')
        print(img_fn)
        
        #remove existing detected component from text
        txtfileloc = os.path.join (maskloc_output_path, os.path.splitext(os.path.basename(img_fn))[0]) + "_loc.txt"
        if os.path.isfile(txtfileloc):
            f =  open(txtfileloc, 'r+')
            textlines = txtremove(f,['IO'])
            f.seek(0)
            f.write(textlines)
            f.truncate()
            f.close()            

        img_raw = cv2.imread(img_fn)
        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
        img_binary = cv2.threshold(img_gray, 128, 255, cv2.THRESH_BINARY)[1]
        img_binary = cv2.subtract(255, img_binary)

        h, w = img_binary.shape[:2]
        img_blank =  np.ones(shape=[h, w], dtype=np.uint8)*255

        _, contours, _ = cv2.findContours(img_binary,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        num_of_IO = 0
        for cnt in contours:
           approx = cv2.approxPolyDP(cnt,epsilon*cv2.arcLength(cnt,True),True)
          
           # Identify all contours with only 5 or 7 vertices and contour area is greater than 500
           if (len(approx)==7 or len(approx)==5) and cv2.contourArea(cnt)>500:
               #cv2.drawContours(img_raw, [approx], 0, (0,255,0), thickness = 1, lineType=8)
               l = len(approx)
               # Iterate all vertices as a arrow tip point
               for it  in range(len(approx)):
                   tip = approx[it][0]
                   othervert = np.delete(approx, it, 0)
                   sumpts = np.zeros(2)
                   for ivert in othervert:
                       sumpts = sumpts + ivert
                   # Calculate the centroid for the rest of symmetric point
                   centpts = sumpts[0]/(l-1)
                   A1 = tip[1]-centpts[1]
                   B1 = -(tip[0]-centpts[0])
                   dis = []
                   
                   for ipt in range(1,int((l+1)/2)):
                       il1 = it + ipt
                       if il1 > l-1:
                           il1 = il1 - l
                       il2 = it - ipt
                       A2 = approx[il2][0][1] - approx[il1][0][1]
                       B2 = -(approx[il2][0][0] - approx[il1][0][0])
                       # Calculate the distance between each of symmetric points 
                       dis.append(np.sqrt(A2**2+B2**2))
                       # Calculate the intersection angle between the line across tip and centroid and the line across two symmetric points
                       theta = abs(np.arccos((A1*A2+B1*B2)/np.sqrt((A1**2+B1**2)*(A2**2+B2**2))))
                       # Check if the line across tip and centroid is perpendicular with the line across two symmetric points with +/- 5 degree accuracy. 
                       # Check if the distance between two symmetric points keep constant or decreasing with +5 pixel accuracy
                       if theta < 80/180*np.pi or theta > 100/180*np.pi or (ipt>1 and dis[ipt-1] - dis[ipt-2] > 5):
                           break
                       if ipt == int((l+1)/2)-1:
                           for item in othervert:
                               cv2.drawMarker(img_raw, (item[0][0], item[0][1]),(0,255,0), markerType=cv2.MARKER_STAR, 
                                markerSize=4, thickness=1, line_type=cv2.LINE_AA)
                           cv2.drawMarker(img_raw, (tip[0], tip[1]),(0,0,255), markerType=cv2.MARKER_STAR, 
                                markerSize=8, thickness=1, line_type=cv2.LINE_AA)
                           cv2.drawMarker(img_raw, (int(centpts[0]), int(centpts[1])),(255,0,0), markerType=cv2.MARKER_STAR, 
                                markerSize=8, thickness=1, line_type=cv2.LINE_AA)
                           # make arrow tip point the first point
                           arrow_cnt = []
                           arrow_cnt.append(approx[it])

                           for ipt in range(1,l):
                               iptt = it + ipt
                               if it + ipt >= l:
                                   iptt = iptt - l
                               arrow_cnt.append(approx[iptt])
                           arrow_cnt = np.array(arrow_cnt)
                           arrow_cnt_scaled = scale_contour(arrow_cnt,1.05)
                           (x,y,w,h) = cv2.boundingRect(arrow_cnt_scaled)
                           cv2.rectangle(img_blank, (x,y), (x+w,y+h), (0), -1)
                           #cv2.drawContours(img_blank, [arrow_cnt_scaled], 0, (0), thickness = -1, lineType=8)
                           num_of_IO += 1
                           with open(txtfileloc, "a") as f:
                                txtline = "IO"
                                txtline += "\t" + str(x+w) + "\t" + str(y+h)
                                txtline += "\t" + str(x) + "\t" + str(y+h)
                                txtline += "\t" + str(x) + "\t" + str(y)
                                txtline += "\t" + str(x+w) + "\t" + str(y)
                                txtline += "\n"
                                f.writelines(txtline)
                                f.close()
        print("Find "+str(num_of_IO)+" inlet/outlet")
        if ifmask:
            img_woIO = cv2.bitwise_or (cv2.bitwise_not(img_blank), cv2.bitwise_not(img_binary), mask = None)
            cv2.imwrite(os.path.join(output_path, os.path.basename(img_fn)), img_woIO)
        else:
            cv2.imwrite(os.path.join(output_path, os.path.basename(img_fn)), img_raw)



def square_detect(input_path,output_path, ifmask, maskloc_output_path):
    """
    Identify the square which is typically intrument alarm.
    """
    epsilon = 0.001
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path)
    img_fn_list = get_images(input_path)
    for img_fn in img_fn_list:
        print('===============')
        print(img_fn)


        img_raw = cv2.imread(img_fn)

        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
        img_binary = cv2.threshold(img_gray, 128, 255, cv2.THRESH_BINARY)[1]

        _, contours, _ = cv2.findContours(img_binary,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            approx = cv2.approxPolyDP(cnt,epsilon*cv2.arcLength(cnt,True),True)
            #for item in approx:
              #  cv2.drawMarker(img_binary, (item[0][0], item[0][1]),(0,255,0), markerType=cv2.MARKER_STAR,markerSize=4, thickness=1, line_type=cv2.LINE_AA)          

            if (len(approx)==4) and cv2.contourArea(cnt)>400:

                cv2.drawContours(img_raw, [approx], 0, (0,255,0), thickness = 3, lineType=8)

               # dis = []
            #    A1 = approx[3][0][1] - approx[1][0][1]
             #   B1 = -(approx[3][0][0] - approx[1][0][0])
            #    dis.append(np.sqrt(A1**2+B1**2))
            #    A2 = approx[2][0][1] - approx[0][0][1]
             #   B2 = -(approx[2][0][0] - approx[0][0][0])
            #    # Calculate the distance between two vertex
            #    dis.append(np.sqrt(A2**2+B2**2))
            #    # Calculate the intersection angle between the line across tip and centroid and the line across two symmetric points
            #    theta = abs(np.arccos((A1*A2+B1*B2)/np.sqrt((A1**2+B1**2)*(A2**2+B2**2))))
             #   # Check if the line across vertex perpendicular with each other. 
             #   # Check if the distance between two vertex points are the same
             #   if theta > 85/180*np.pi and theta < 95/180*np.pi and np.abs(dis[0] - dis[1]) < 5:
            #        for item in approx:
             #           cv2.drawMarker(img_raw, (item[0][0], item[0][1]),(0,255,0), markerType=cv2.MARKER_STAR,markerSize=4, thickness=1, line_type=cv2.LINE_AA)

        cv2.imwrite(os.path.join(output_path, os.path.basename(img_fn)), img_raw)

def circle_detect(input_path,output_path, ifmask, maskloc_output_path):
    """
    Identify the circles using houghcircle approach
    ifmast ==  True, the area will be masked in output drawing
    """
    print("========== detect circle ==============")
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path)
    img_fn_list = get_images(input_path)
    for img_fn in img_fn_list:
        print('===============')
        print(img_fn)
        #remove existing detected component from text
        txtfileloc = os.path.join (maskloc_output_path, os.path.splitext(os.path.basename(img_fn))[0]) + "_loc.txt"
        if os.path.isfile(txtfileloc):
            f =  open(txtfileloc, 'r+')
            textlines = txtremove(f,['CIR'])
            f.seek(0)
            f.write(textlines)
            f.truncate()
            f.close()            

        img_raw = cv2.imread(img_fn)
        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
        num_of_cir = 0
        # apply automatic Canny edge detection using the computed median
        circles = cv2.HoughCircles(img_gray,cv2.HOUGH_GRADIENT,1.8,100,  
                                   param1=200, param2=80,minRadius=9,maxRadius=60)

        h, w = img_gray.shape[:2]
        img_blank =  np.ones(shape=[h, w], dtype=np.uint8)*255
        img_blank2 = img_blank.copy()
        # pixel width of each circle
        wl =3

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for cir in circles[0,:]:
                cv2.circle(img_blank, (cir[0],cir[1]), int(cir[2]+wl), 0, -1)  # -1 to draw filled circles
                cv2.circle(img_blank, (cir[0],cir[1]), int(cir[2]-wl), 255, -1)  # -1 to draw filled circles

            bit_or = cv2.bitwise_or(img_blank, img_gray, mask = None)
            #cv2.imwrite(os.path.join(output_path, "cir"+"-"+os.path.basename(img_fn)), bit_or) 
            bit_or = cv2.threshold(bit_or, 128, 255, cv2.THRESH_BINARY)[1]
            bit_or= cv2.subtract(255, bit_or)
            
            for cir in  circles[0,:]:
                circheck = []
                for iy in range(cir[1]-cir[2]-1,cir[1]+cir[2]+1):
                    countblkpixel1 = np.sum(bit_or[iy,cir[0]-cir[2]-wl:cir[0]]!= 0)
                    countblkpixel2 = np.sum(bit_or[iy,cir[0]:cir[0]+cir[2]+wl]!= 0)
                    if countblkpixel1 > 1:
                        circheck.append(1)
                    else:
                        circheck.append(0)
                    if countblkpixel2 > 1:
                        circheck.append(1)
                    else:
                        circheck.append(0)
                # check if each ring contain a circle
                if np.sum(circheck)*1.0/len(circheck) > 0.9:
                    # draw the outer circle
                    cv2.circle(img_raw,(cir[0],cir[1]),cir[2],(0,255,0),2)                
                    # draw the center of a cirlce
                    cv2.circle(img_raw,(cir[0],cir[1]),2,(0,0,255),3)
                    cv2.circle(img_blank2, (cir[0],cir[1]), int(cir[2]+wl), 0, -1)  # -1 to draw filled circles
                    # draw bounding box to cover the circle
                    cir[2] +=wl
                    bbox_scaled = [cir[0]+cir[2],cir[1]+cir[2],cir[0]-cir[2],cir[1]+cir[2],cir[0]-cir[2],cir[1]-cir[2],cir[0]+cir[2],cir[1]-cir[2]]
                    num_of_cir += 1
                    with open(txtfileloc, "a") as f:
                        txtline = "CIR"
                        for ip in bbox_scaled:
                            txtline += "\t" + str(ip)
                        txtline += "\n"
                        f.writelines(txtline)
                        f.close()                   
        print("Find "+str(num_of_cir)+" circles")
        if ifmask:
            img_woCIR = cv2.bitwise_or(cv2.bitwise_not(img_blank2), img_gray, mask = None)
            cv2.imwrite(os.path.join(output_path, os.path.basename(img_fn)), img_woCIR)
        else:
            cv2.imwrite(os.path.join(output_path, os.path.basename(img_fn)), img_raw)

