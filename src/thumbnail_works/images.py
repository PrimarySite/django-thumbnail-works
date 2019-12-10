# -*- coding: utf-8 -*-

import os
import io
import logging

try:
    from PIL import Image, ImageFilter
except ImportError:
    import Image
    import ImageFilter

from django.core.files.base import ContentFile

from thumbnail_works import settings

from thumbnail_works.exceptions import ThumbnailOptionError
from thumbnail_works.exceptions import ThumbnailWorksError
from thumbnail_works.utils import get_width_height_from_string
from thumbnail_works.cropresize import crop_resize


logger = logging.getLogger(__name__)


class ImageProcessor:
    """Adds image processing support to ImageFieldFile or derived classes.

    Required instance attributes::

        self.identifier
        self.proc_opts
        self.name
        self.storage

    """

    DEFAULT_OPTIONS = {
        'size': None,
        'sharpen': False,
        'detail': False,
        'upscale': False,
        'format': settings.THUMBNAILS_FORMAT,
        }

    def setup_image_processing_options(self, proc_opts):
        """Sets the image processing options as an attribute of the
        ImageFieldFile instance.

        If ``proc_opts`` is ``None``, then ``self.proc_opts`` is also set to
        ``None``. This is allowed in favor of the source image which may not be
        processed.

        This method checks the provided options and also ensures that the
        final dictionary contains all the supported options with a default
        or a user-defined value.

        """
        if proc_opts is None:
            if self.identifier is not None: # self is a thumbnail
                raise ThumbnailOptionError('It is not possible to set the \
                    image processing options to None on thumbnails')
            self.proc_opts = None
        elif not isinstance(proc_opts, dict):
            raise ThumbnailOptionError('A dictionary object is required')
        else:
            for option in proc_opts.keys():
                if option not in self.DEFAULT_OPTIONS.keys():
                    raise ThumbnailOptionError('Invalid thumbnail option `%s`' % option)
            self.proc_opts = self.DEFAULT_OPTIONS.copy()
            self.proc_opts.update(proc_opts)

    def get_image_extension(self):
        """Returns the extension in accordance to the image format.

        If the image processing options ``self.proc_opts`` is not a dict,
        None is returned.

        """
        if not isinstance(self.proc_opts, dict):
            return

        ext = self.proc_opts['format']
        if ext:
            ext = ext.lower()

        if ext == 'jpeg':
            return '.jpg'
        return '.%s' % ext

    def generate_image_name(self, name, force_ext=None):
        """Generates a path for the image file taking the format into account.

        This method should be used by both the source image and thumbnails
        to get their ``name`` attribute.

        Arguments
        ---------

        ``name``
            A relative path to MEDIA_ROOT. ``name`` cannot be empty or None.
            In such a case a ``ThumbnailWorksError`` is raised.
        ``force_ext``
            Can be used to force a specific extension. By default, the extension
            is derived from the user-specified image format and is generated by
            the ``get_image_extension()`` method.

        Path transformation logic
        -------------------------

        Path transformation logic for source image and thumbnails.

        - Assuming ``name = 'images/photo.jpg'``:

          - source: images/photo.<extension>
          - thumbnail: images/<THUMBNAILS_DIRNAME>/photo.<identifier>.<extension>

        """
        if not name:
            raise ThumbnailWorksError('The provided name is not usable')

        root_dir = os.path.dirname(name)  # images
        filename = os.path.basename(name)    # photo.jpg
        base_filename, default_ext = os.path.splitext(filename)

        if force_ext is not None:
            ext = force_ext
            logger.debug('Forcing file extension: `{}`'.format(ext))

        else:
            ext = self.get_image_extension()
            if ext is None:
                ext = default_ext

        self.ext = ext

        if self.identifier is None: # For source images
            image_filename = '%s%s' % (base_filename, ext)
            return os.path.join(root_dir, image_filename)

        else:   # For thumbnails
            image_filename = '%s.%s%s' % (base_filename, self.identifier, ext)
            if settings.THUMBNAILS_DIRNAME:
                return os.path.join(root_dir, settings.THUMBNAILS_DIRNAME, image_filename)
            return os.path.join(root_dir, image_filename)

    def get_image_content(self):
        """Returns the image data as a ContentFile."""
        try:
            content = ContentFile(self.storage.open(self.name).read())
        except IOError:
            raise Exception('Could not access image data: %s' % self.name)
        else:
            return content

    def process_image(self, content=None):
        """Processes and returns the image data."""

        if content is None:
            content = self.get_image_content()

        # Image.open() accepts a file-like object, but it is needed
        # to rewind it back to be able to get the data,
        if content.closed:
            content = self.source.get_image_content()
        content.seek(0)
        im = Image.open(content)

        # Convert to RGB format
        if im.mode not in ('L', 'RGB', 'RGBA'):
            im = im.convert('RGB')

        # Process
        size = self.proc_opts['size']
        upscale = self.proc_opts['upscale']

        if size is not None:
            new_size = size
            im = self._resize(im, new_size, upscale)

        sharpen = self.proc_opts['sharpen']
        if sharpen:
            im = self._sharpen(im)

        detail = self.proc_opts['detail']
        if detail:
            im = self._detail(im)

        # Save image data
        format = self.proc_opts['format'] or self.ext
        buffer = io.BytesIO()

        if format == 'JPEG':
            im.save(buffer, format, quality=settings.THUMBNAILS_QUALITY)
        else:
            im.save(buffer, format)

        data = buffer.getvalue()

        return ContentFile(data)

    # Processors

    def _resize(self, im, size, upscale):
        return crop_resize(im, size, exact_size=upscale)

    def _sharpen(self, im):
        return im.filter(ImageFilter.SHARPEN)

    def _detail(self, im):
        return im.filter(ImageFilter.DETAIL)

