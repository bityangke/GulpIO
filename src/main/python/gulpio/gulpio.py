#!/usr/bin/env python

import os
import cv2
import pickle
import numpy as np

from PIL import Image
from collections import namedtuple, defaultdict


ImgInfo = namedtuple('ImgInfo', ['loc',
                                 'pad',
                                 'length'])
MetaInfo = namedtuple('MetaInfo', ['id_',
                                   'meta_data'])


class GulpVideoIO(object):

    def __init__(self, path, flag, meta_path, img_info_path):
        self.meta_path = meta_path
        self.img_info_path = img_info_path
        self.path = path
        self.flag = flag
        self.is_open = False
        self.is_writable = False
        self.f = None
        self.img_dict = None
        self.meta_dict = None

    def get_or_create_dict(self, path):
        if os.path.exists(path):
            return pickle.load(open(path, 'rb'))
        return defaultdict()

    def open(self):
        self.meta_dict = self.get_or_create_dict(self.meta_path)
        self.img_dict = self.get_or_create_dict(self.img_info_path)

        if self.flag == 'wb':
            self.f = open(self.path, self.flag)
            self.is_writable = True
        elif self.flag == 'rb':
            self.f = open(self.path, self.flag)
            self.is_writable = False
        self.is_open = True

    def close(self):
        if self.is_open:
            pickle.dump(self.meta_dict, open(self.meta_path, 'wb'))
            pickle.dump(self.img_dict, open(self.img_info_path, 'wb'))
            self.f.close()
            self.is_open = False
        else:
            return

    def write_meta(self, vid_idx, id_, meta_data):
        assert self.is_writable
        meta_info = MetaInfo(meta_data=list(meta_data),
                             id_=id_)
        self.meta_dict[vid_idx] = [meta_info]

    def write(self, vid_idx, id_, image):
        assert self.is_writable
        loc = self.f.tell()
        img_str = cv2.imencode('.jpg', image)[1].tostring()
        pad = 4 - (len(img_str) % 4)
        record = img_str.ljust(len(img_str) + pad, b'\0')
        img_info = ImgInfo(loc=loc,
                           length=len(record),
                           pad=pad)
        try:
            self.img_dict[vid_idx].append(img_info)
        except KeyError:
            self.img_dict[vid_idx] = [img_info]
        self.f.write(record)

    def read(self, img_info):
        assert not self.is_writable
        self.f.seek(img_info.loc)
        record = self.f.read(img_info.length)
        img_str = record[:-img_info.pad]
        nparr = np.fromstring(img_str, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img)

    def reset(self):
        self.close()
        self.open()

    def seek(self, loc):
        self.f.seek(loc)
