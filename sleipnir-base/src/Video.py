import PySide
from PySide import QtCore, QtGui
import os
import cv2 as cv
import numpy
import time

class Video:

   def __init__(self, cam, flight_directory, widgetVideo, buttonPlayForward, buttonPlayBackward, buttonPause, buttonFind, buttonForwardStep, buttonBackStep, slider, buttonCopy, labelTime):

      # Frame number in video
      self.current_frame_number = 0

      # Find flag
      self.find = False

      # Currently found motion
      self.found_motion = 0

      # Motion direction
      self.direction = 0

      # Currently shooting
      self.shooting = False

      # Forward / Backward flag
      self.forward = True

      # cam1 or cam2
      self.cam = cam

      # Directory of flight
      self.flight_directory = flight_directory

      # Timestamp to start video on, this is the higest number of the two cameras
      self.start_timestamp = 0

      # Ground level, no motion track below this
      self.groundlevel = 400

      self.last_motion_view_frame = 0


      # Lots of widgets
      self.widgetVideo = widgetVideo
      self.buttonPlayForward = buttonPlayForward
      self.buttonPlayForward.clicked.connect(self.__onPlayForward)
      self.buttonPlayBackward = buttonPlayBackward
      self.buttonPlayBackward.clicked.connect(self.__onPlayBackward)
      self.buttonFind = buttonFind
      self.buttonFind.clicked.connect(self.__onFind)
      self.buttonForwardStep = buttonForwardStep
      self.buttonForwardStep.clicked.connect(self.__onForwardStep)
      self.buttonBackStep = buttonBackStep
      self.buttonBackStep.clicked.connect(self.__onBackStep)
      self.buttonPause = buttonPause
      self.buttonPause.clicked.connect(self.__onPause)
      self.slider = slider
      self.slider.sliderMoved.connect(self.__onSliderChanged)
      self.buttonCopy = buttonCopy
      self.buttonCopy.clicked.connect(self.__onCopy)
      self.labelTime = labelTime

      # Timer for playing video
      self.timer = QtCore.QTimer(self.widgetVideo)
      self.timer.timeout.connect(self.__timerplay)

      self.frame_processing_worker = FrameProcessingWorker(self)
      self.frame_processing_worker.start()

   # Sibling video is the Video instance of the other camera
   def set_sibling_video(self, sibling_video):
      self.sibling_video = sibling_video

   # Reset parameters
   def reset(self):
      self.current_frame_number = 1
      self.find = False
      self.comparison_image_cv = None
      self.comparison_image_frame_count = 0 
      self.found_motion = 0
      self.direction = 0

   # Set this Video instance to shooting, mening realtime view of data
   def set_shooting(self, shooting):
      self.direction = 0
      self.shooting = shooting
      if (self.shooting):
         self.buttonPlayForward.setEnabled(False)
         self.buttonPlayBackward.setEnabled(False)
         self.buttonFind.setEnabled(False)
         self.buttonForwardStep.setEnabled(False)
         self.buttonBackStep.setEnabled(False)
         self.buttonPause.setEnabled(False)
         self.slider.setEnabled(False)
         self.buttonCopy.setEnabled(False)

      if (self.shooting == False):
         self.slider.setMinimum(1)
         self.slider.setMaximum(self.cameras_data.get_last_frame(self.cam))
         self.buttonPlayForward.setEnabled(True)
         self.buttonPlayBackward.setEnabled(True)
         self.buttonFind.setEnabled(True)
         self.buttonForwardStep.setEnabled(True)
         self.buttonBackStep.setEnabled(True)
         self.buttonPause.setEnabled(True)
         self.slider.setEnabled(True)
         self.buttonCopy.setEnabled(True)

   # Returns current frame number of video
   def get_current_frame_number(self):
      return self.current_frame_number

   # Sets current frame number of video
   def set_current_frame_number(self, frame_number):
      self.current_frame_number = frame_number
      self.update()

   # Returns a video frame as a cv image and it's timestamp
   def getFrame(self, frame_number, use_image = None):
      file = self.flight_directory + "/" + str((frame_number / 100) *100).zfill(6)
      if not os.path.exists(file):
         return None
      timestamp = self.cameras_data.get_timestamp_from_frame_number(self.cam, frame_number)
      if use_image is not None:
         image_cv = use_image
      else:
         picture_filename = self.flight_directory + "/" + str((frame_number / 100) *100).zfill(6) + "/image" + str(frame_number).zfill(9) + ".jpg"
         image_cv = cv.imread(picture_filename, 0)
      return { "timestamp": int(timestamp), "image": image_cv }

   # Set the start timestamp
   def setStartTimestamp(self, start_timestamp):
      self.start_timestamp = start_timestamp

   # Copy button, set the timestamp of the sibling video to this on
   def __onCopy(self):
      timestamp_this = self.cameras_data.get_timestamp_from_frame_number(self.cam, self.current_frame_number)
      for i in range(1, self.cameras_data.get_last_frame(self.sibling_video.cam) + 1):
         timestamp_sibling = self.cameras_data.get_timestamp_from_frame_number(self.sibling_video.cam, i)
         if timestamp_sibling >= timestamp_this:
            break
      self.sibling_video.set_current_frame_number(i)
      self.sibling_video.direction = 0

   def __onSliderChanged(self, value):
      self.direction = 0
      self.current_frame_number = value
      self.update()
      self.timer.stop()

   def __onPlayForward(self):
      self.direction = 0
      self.find = False
      self.forward = True
      self.timer.start(11)

   def __onPlayBackward(self):
      self.direction = 0
      self.find = False
      self.forward = False
      self.timer.start(11)

   def __onPause(self):
      self.direction = 0
      self.timer.stop()
      self.update()

   def __onFind(self):
      self.find = True
      self.found_motion = False
      self.forward = True
      self.timer.start(0)

   def __onForwardStep(self):
      self.direction = 0
      if self.current_frame_number < self.cameras_data.get_last_frame(self.cam):
         self.current_frame_number += 1
      self.timer.stop()
      self.update()

   def __onBackStep(self):
      self.direction = 0
      if self.current_frame_number > 1:
         self.current_frame_number -= 1
      self.timer.stop()
      self.update()

   def __timerplay(self):
      image = None

      if self.forward:
         self.current_frame_number += 1
         if self.current_frame_number > self.cameras_data.get_last_frame(self.cam):
            self.current_frame_number = self.cameras_data.get_last_frame(self.cam)
            self.find = False
      else:
         self.current_frame_number -= 1
         if (self.current_frame_number < 1):
            self.current_frame_number  =1
            self.find = False

      frame = self.getFrame(self.current_frame_number)
      if not frame:
         return
      image_cv = frame["image"];

      if self.forward:
         motion = self.have_motion(image_cv)
         if self.find:
            image = motion["image"]
            if motion["motion"]:
               self.timer.stop()
               self.update(image)

      if self.find and self.current_frame_number & 7 == 1:
         self.update(image)
      elif not self.find:
         self.update(image)         

   def have_motion(self, image_cv):

      while self.frame_processing_worker.is_processing():
         time.sleep(0.001)

      if self.direction < 0:
         self.direction +=1

      if self.direction > 0:
         self.direction -=1

      self.frame_processing_worker.image_cv = image_cv
      self.frame_processing_worker.current_frame_number = self.current_frame_number
      self.frame_processing_worker.start_processing()
      image = self.frame_processing_worker.image
      found_motion = self.frame_processing_worker.found_motion

      return { "motion": found_motion, "image": image, "frame_number": self.frame_processing_worker.found_motion_frame_number }

   def view_frame(self, frame_number):
      self.current_frame_number = frame_number
      self.update()

   def view_frame_motion_track(self, frame_number, live_preview = True):
      self.current_frame_number = frame_number
      frame = self.getFrame(self.current_frame_number)
      if not frame:
         return
      image_cv = frame["image"];
      motion = self.have_motion(image_cv)
      image = motion["image"]
      # Only show every other frame
      if live_preview and self.current_frame_number & 1 == 1:
         self.update(image)
      if motion["motion"]:
         return { "frame_number": motion["frame_number"], "direction": self.direction / abs(self.direction) }
      return None

   def update(self, use_image = None):
      frame = self.getFrame(self.current_frame_number, use_image = use_image)
      if not frame:
         return

      local_timestamp = frame["timestamp"] - self.start_timestamp
      if (local_timestamp < 0):
         local_timestamp = 0
      self.labelTime.setText(self.__format_time(local_timestamp))

      if (self.shooting):
         self.slider.setSliderPosition(1)
      else:
         self.slider.setSliderPosition(self.current_frame_number)

      # Draw center line
      cv.rectangle(frame["image"], (160, 0), (160, 480), (0, 0, 0), 1)

      image_qt = QtGui.QImage(frame["image"], frame["image"].shape[1], frame["image"].shape[0], frame["image"].strides[0], QtGui.QImage.Format_Indexed8)
      self.widgetVideo.setPixmap(QtGui.QPixmap.fromImage(image_qt))

   def __format_time(self, ms):
      return "%02d:%02d:%03d" % (int(ms / 1000) / 60, int(ms / 1000) % 60, ms % 1000)


class FrameProcessingWorker(QtCore.QThread):

   def __init__(self, video):
      self.processing = False

      # Video instance
      self.video = video
      # Iamge cv needed for processing
      self.image_cv = None

      # Comparision for motion tracking
      self.comparison_image_cv = None

      # Motion boxes for all frames
      self.motion_boxes = {}

      # Frame number
      self.current_frame_number = 0

      # Found motion on frame number
      self.found_motion_frame_number = 0

      # Image returned by the have motion
      self.image = None

      # Found motion returned
      self.found_motion = False

      QtCore.QThread.__init__(self)


   def run(self):
      while True:
         if not self.processing:
            time.sleep(0.001)
            continue

         image = None
         image_gray_cv = self.image_cv
         image_blur_cv = cv.GaussianBlur(image_gray_cv, (13, 13), 0)
         found_motion = False

         if self.comparison_image_cv is not None:

            frame_delta = cv.absdiff(self.comparison_image_cv, image_blur_cv)
            threshold = cv.threshold(frame_delta, 2, 255, cv.THRESH_BINARY)[1]
            threshold = cv.dilate(threshold, None, iterations=3)
            (self.motion_boxes[self.current_frame_number], _) = cv.findContours(threshold.copy(), cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
#            print len(self.motion_boxes[self.current_frame_number])

            #DEBUG  MOTION TRACK
#            if len(self.motion_boxes[self.current_frame_number]) > 30:
            if False:
               if (self.video.direction == 0):
                  found_motion = True
                  self.video.direction = 90*6
            else:
               for c in self.motion_boxes[self.current_frame_number]:
                  found_motion = False
                  (x, y, w, h) = cv.boundingRect(c)

                  # Set ground level
                  if y > self.video.groundlevel:
                     continue


                  if cv.contourArea(c) < 15:
                     continue
                  if cv.contourArea(c) > 10000:
                     continue
                  if x < 160 and x + w > 160:
                     found_motion = True

                  cv.rectangle(image_gray_cv, (x - 2, y - 2), (x + w + 4, y + h + 4), (0, 0, 0), 2)

                  if found_motion and self.current_frame_number > 4 and self.video.direction == 0:
                     # Check previous motion boxes
                     direction = self.check_overlap_previous(x, y, w, h, x, w, self.current_frame_number - 1, 10)

                     self.video.direction = direction * 90 * 6
#                     if self.video.direction != 0:
#                        print self.video.direction

                     if (self.video.direction != 0):
                        found_motion = True
                        break
                     else:
                        found_motion = False
                  else:
                     found_motion = False

         self.comparison_image_cv = image_blur_cv
         self.image = image_gray_cv
         self.found_motion = found_motion
         self.found_motion_frame_number = self.current_frame_number

#         time.sleep(0.4)
         # Close processing
         self.processing = False

   def check_overlap_previous(self, x, y, w, h, x1, w1, frame_number, iterations):
#      print "check overlap: " + str(frame_number) + " iteration: " + str(iterations)
      if not frame_number in self.motion_boxes:
         return 0
      for c2 in self.motion_boxes[frame_number]:
         (x2, y2, w2, h2) = cv.boundingRect(c2)

         if cv.contourArea(c2) < 15:
            continue
         if cv.contourArea(c2) > 10000:
            continue

         if x == x2 and y == y2 and w == w2 and h == h2 :
            continue

         # Sanity on size
         if w < 5 or h < 5 or w > 100 or h > 100:
            continue

         # the sizes of the boxes can't be too far off
         d1 = float(w * h)
         d2 = float(w2 * h2)
         diff = min(d1, d2) / max(d1, d2)
         if diff < 0.3:
            continue
 #        print "size diff: " + str(diff)
 
         if (self.overlap_box(x, y, w, h, x2, y2, w2, h2) == 0):
            continue

         # if iterations is zero or object is coming to close to the side
         if iterations == 0 or x2 < 20 or x2 + w2 > 300:
            if x1 + w1 < x2 + w2:
               return -1;
            else:
               return 1
         return self.check_overlap_previous(x2, y2, w2, h2, x1, w1, frame_number - 1, iterations -1)
      return 0

   # Return 0 on non overlap
   def overlap_box(self, x, y, w, h, x2, y2, w2, h2):
      if (x + w < x2):    # c is left of c2
         return 0
      if (x > x2 + w2):   # c is right of c2
         return 0
      if (y + h < y2):    # c is above c2
         return 0
      if (y > y2 + h2):   # c is below c2                        
         return 0

      # Find direction from first frame
      if x + w < x2 + w2:
         return -1;
      else:
         return 1   
   
   def start_processing(self):
      self.processing = True

   def is_processing(self):
      return self.processing
