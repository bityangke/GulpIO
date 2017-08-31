import os
import numpy as np
import json
from .fileio import GulpDirectory


class GulpIOEmptyFolder(Exception):  # pragma: no cover
        pass


class GulpVideoDataset(object):

    def __init__(self, data_path, num_frames, step_size,
                 is_val, transform=None, target_transform=None, stack=True,
                 random_offset=True):
        r"""Simple data loader for GulpIO format.

            Args:
                data_path (str): path to GulpIO dataset folder
                label_path (str): path to GulpIO label dictionary matching
            label ids to label names
                num_frames (int): number of frames to be fetched.
                step_size (int): number of frames skippid while picking
            sequence of frames from each video.
                is_va (bool): sets the necessary augmention procedure.
                transform (object): set of augmentation steps defined by
            Compose(). Default is None.
                target_transform (func): performs preprocessing on labels if
            defined. Default is None.
                stack (bool): stack frames into a numpy.array. Default is True.
                random_offset (bool): random offsetting to pick frames, if
            number of frames are more than what is necessary.
        """

        self.gd = GulpDirectory(data_path)
        self.items = list(self.gd.merged_meta_dict.items())
        self.label2idx = json.load(open(os.path.join(data_path,
                                                     'label2idx.json')))
        self.num_chunks = self.gd.num_chunks

        if self.num_chunks == 0:
            raise(GulpIOEmptyFolder("Found 0 data binaries in subfolders " +
                                    "of: ".format(data_path)))

        print(" > Found {} chunks".format(self.num_chunks))
        self.data_path = data_path
        self.classes = self.label2idx.keys()
        self.transform_video = transform
        self.target_transform = target_transform
        self.num_frames = num_frames
        self.step_size = step_size
        self.is_val = is_val
        self.stack = stack
        self.random_offset = random_offset

    def __getitem__(self, index):
        """
        With the given video index, it fetches frames. This functions is called
        by Pytorch DataLoader threads. Each Dataloader thread loads a single
        batch by calling this function per instance.
        """
        item_id, item_info = self.items[index]

        target_name = item_info['meta_data'][0]['label']
        target_idx = self.label2idx[target_name]
        frames = item_info['frame_info']
        num_frames = len(frames)
        # set number of necessary frames
        if self.num_frames > -1:
            num_frames_necessary = self.num_frames * self.step_size
        else:
            num_frames_necessary = num_frames
        offset = 0
        if num_frames_necessary < num_frames and self.random_offset:
            # If there are more frames, then sample starting offset.
            diff = (num_frames - num_frames_necessary)
            # temporal augmentation
            if not self.is_val:
                offset = np.random.randint(0, diff)
        # set target frames to be loaded
        frames_slice = slice(offset, num_frames_necessary + offset,
                             self.step_size)
        frames, meta = self.gd[item_id, frames_slice]
        # padding last frame
        if num_frames_necessary > num_frames:
            # Pad last frame if video is shorter than necessary
            frames.extend([frames[-1]] * (num_frames_necessary - num_frames))
        # augmentation
        if self.transform_video:
            frames = self.transform_video(frames)
        # format data to torch tensor
        if self.stack:
            imgs = np.stack(frames)
        return (imgs, target_idx)

    def __len__(self):
        """
        This is called by PyTorch dataloader to decide the size of the dataset.
        """
        return self.num_chunks


class GulpImageDataset(object):

    def __init__(self, data_path, is_val=False, transform=None,
                 target_transform=None):
        r"""Simple image data loader for GulpIO format.

            Args:
                data_path (str): path to GulpIO dataset folder
                label_path (str): path to GulpIO label dictionary matching
            label ids to label names
                is_va (bool): sets the necessary augmention procedure.
                transform (object): set of augmentation steps defined by
            Compose(). Default is None.
                target_transform (func): performs preprocessing on labels if
            defined. Default is None.
        """

        self.chunk_paths, self.meta_paths, self.label_to_idx = find_gulp_files(data_path)
        self.num_chunks = len(self.chunk_paths)

        if len(self.chunk_paths) == 0:
            raise(GulpIOEmptyFolder("Found 0 data binaries in subfolders " +
                                    "of: ".format(data_path)))

        if len(self.chunk_paths) != len(self.meta_paths):
            raise(GulpIOMismatch("Number of binary files are not matching " +
                                 "with number of meta files. Check GulpIO " +
                                 "dataset."))

        print(" > Found {} chunks".format(self.num_chunks))
        self.data_path = data_path
        self.meta_dict = merge_meta_files(self.meta_paths)
        self.classes = self.label_to_idx.keys()
        self.transform = transform
        self.target_transform = target_transform
        self.is_val = is_val

    def __getitem__(self, index):
        """
        With the given video index, it fetches frames. This functions is called
        by Pytorch DataLoader threads. Each Dataloader thread loads a single
        batch by calling this function per instance.
        """
        item_idx, item_info = self.meta_dict[index]
        chunk_path = os.path.join(self.data_path, item_info['chunk_file'])
        chunk_file = open(chunk_path, "rb")
        target_name = item_info['meta_data'][0]['label']
        target_idx = self.label_to_idx[target_name]
        image = item_info['frame_info']
        assert len(image) > 0
        # read image
        img = self.__read_image(image[0], chunk_file)
        # augmentation
        if self.transform:
            img = self.transform(img)
        chunk_file.close()
        return (img, target_idx)

    def __len__(self):
        """
        This is called by PyTorch dataloader to decide the size of the dataset.
        """
        return len(self.meta_dict)

    def __read_image(self, meta_info, f):
        """
        Reads single frames from a video
        """
        # TODO: read item by gulpio api
        loc, pad, length = meta_info
        f.seek(loc)
        record = f.read(length)
        if pad == 0:
            img_str = record
        else:
            img_str = record[:-pad]
        nparr = np.fromstring(img_str, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_ANYCOLOR)
        if img.ndim > 2:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img
