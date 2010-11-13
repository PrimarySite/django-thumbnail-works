# -*- coding: utf-8 -*-
#
#  This file is part of django-thumbnail-works.
#
#  django-thumbnail-works provides an enhanced ImageField that generates and
#  manages thumbnails of the uploaded image.
#
#  Development Web Site:
#    - http://www.codetrax.org/projects/django-thumbnail-works
#  Public Source Code Repository:
#    - https://source.codetrax.org/hgroot/django-thumbnail-works
#
#  Copyright 2010 George Notaras <gnot [at] g-loaded.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import copy
import StringIO
from PIL import Image

from django.db.models.fields.files import ImageField, ImageFieldFile
from django.core.files.base import ContentFile
from django.core.files import File

from thumbnail_works.exceptions import ImageSizeError
from thumbnail_works.utils import get_width_height_from_string, get_thumbnail_path
from thumbnail_works import settings
from thumbnail_works import image_processors



class ImageObject:
    
    def get_img_data_from_file(self, f_obj):
        
        # PIL_Image.open() accepts a file-like object, but it is needed
        # to rewind it back to be able to get the data
        f_obj.seek(0)
        im = Image.open(f_obj)
        
        # Convert to RGB if necessary
        if im.mode not in ('L', 'RGB', 'RGBA'):
            im = im.convert('RGB')
        
        return im
    
    def get_file_for_img_data(self, im):
        
        io = StringIO.StringIO()
    
        if settings.THUMBNAILS_FORMAT == 'JPEG':
            im.save(io, 'JPEG', quality=settings.THUMBNAILS_QUALITY)
        elif settings.THUMBNAILS_FORMAT == 'PNG':
            im.save(io, 'PNG')
        
        return ContentFile(io.getvalue())
        #return File(io)
    
    
class Thumbnail:
    
    def __init__(self, name, size, source):
        self.name = self._get_name(name)    # the thumbnail name as set in the dictionary
        self.width, self.height = get_width_height_from_string(size)
        self.url = get_thumbnail_path(source.url, self.name)
    
    def _get_name(self, name):
        return name.replace(' ', '_')

        
class EnhancedImageFieldFile(ImageFieldFile):
    
    def __init__(self, *args, **kwargs):
        super(EnhancedImageFieldFile, self).__init__(*args, **kwargs)
        
        # Set thumbnail objects as instance attributes
        if self.field.thumbnails:
            for thumbnail_name, thumbnail_size in self.field.thumbnails.items():
                thumbnail_obj = Thumbnail(thumbnail_name, thumbnail_size, self)
                setattr(self, thumbnail_name, thumbnail_obj)
    
    def save(self, name, content, save=True):
        """
        name: is the path on the filesystem of the original image
        """
        
        
        # Before saving, resize the source image if a size has been set
        #content = copy.copy(content)
        img_obj = ImageObject()
        im = img_obj.get_img_data_from_file(content)
        im = image_processors.resize(im, self.field.resize_source)
        im = image_processors.sharpen(im)
        content = img_obj.get_file_for_img_data(im)
        
        
        super(EnhancedImageFieldFile, self).save(name, content, save)
        
        # self.name has been re-set in the save() above
        # use self.name to generate the thumbnail filename
        
        """
        # Generate thumbnails
        if self.field.thumbnails:
            for thumbnail_name, thumbnail_size in self.field.thumbnails.items():
                new_content = copy.copy(content)
                img_obj = ImageObject()
                im = img_obj.get_img_data_from_file(new_content)
                image_processors.resize(im, thumbnail_size)
                new_content = img_obj.get_file_for_img_data(im)
                path = get_thumbnail_path(self.name, thumbnail_name)
                path_saved = self.storage.save(name, content)
                
                # check if path == path_saved
         """
                
    def delete(self, save=True):
        source_path = copy.copy(self.name)
        super(EnhancedImageFieldFile, self).delete(save)
        
        """
        # Delete thumbnails
        if self.field.thumbnails:
            for thumbnail_name, thumbnail_size in self.field.thumbnails.items():
                path = get_thumbnail_path(source_path, thumbnail_name)
                self.storage.delete(path)
                
      """


class EnhancedImageField(ImageField):
    attr_class = EnhancedImageFieldFile
    
    def __init__(self, resize_source=None, thumbnails={}, **kwargs):
        """
        resize_source: image size in WIDTHxHEIGHT. If set, the uploaded image
        will be resized to this size.
        
        Thumbnails format:
        
            <thumbnail_name> : <size>
        
        """
        self.resize_source = resize_source
        self.thumbnails = thumbnails
        super(EnhancedImageField, self).__init__(**kwargs)

