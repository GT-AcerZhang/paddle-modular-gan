from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
from pmgan import utils
import gin
import six

from paddle.fluid import dygraph as dg


class LayerApply(abc.ABCMeta):
  """Meta class that runs 'apply' method after class instance created for paddle dygraph Layer class.
  """
  
  def __new__(cls, name, bases, attrs):
    if "__init__" in attrs:
      __init_originl__ = attrs["__init__"]
      def __init__(self, *args, **kwargs):
        if not hasattr(self, "_dg_layer_initialized_status"):
          dg.Layer.__init__(self)
          self._dg_layer_initialized_status = True
        __init_originl__(self, *args, **kwargs)
      attrs["__init__"] = __init__
      
    return type.__new__(cls, name, bases, attrs)
    
  def __call__(cls, *args, **kwargs):
    instance = super().__call__(*args, **kwargs)
    instance.apply()
    return instance
    

@six.add_metaclass(LayerApply)
class Module(dg.Layer):
  """Base class for architectures.
  """
  def __init__(self, name):
    self._name = name

  @property
  def name(self):
    return self._name

  @property
  def trainable_parameters(self):
    return list(filter(lambda x: x.stop_gradient==False and x.trainable==True, self.parameters()))
    
  @abc.abstractmethod
  def apply(self):
    """Method to run after the module class initialized for building the module.
    """

  def add_sublayer(*args):
    """Method to add named sub module 
    """
    assert len(args) > 0
    if len(args) == 1:
      sublayer = args[0]
      name = None
    elif isinstance(args[0], dg.Layer):
      sublayer, name = args[:2]
    else:
      name, sublayer = args[:2]
    if name is None:
      assert sublayer.name is not None, "sublayer should have a name"
      name = sublayer
    if hasattr(self, name):
      i = 1
      while True:
        suffix = str(i)
        if not hasattr(self, name + "_" + suffix):
          name = name + "_" + suffix
          break
        i += 1
    sublayer = super().add_sublayer(name, sublayer)

    return lambda *args, **kwargs: sublayer(*args, **kwargs)

@gin.configurable("G", blacklist=["name", "image_shape"])
class AbstractGenerator(Module):
  """Interface for generator architectures."""

  def __init__(self,
               name="generator",
               image_shape=None,
               batch_norm_cls=None,
               spectral_norm=False):
    """Constructor for all generator architectures.
    Args:
      name: Scope name of the generator.
      image_shape: Image shape to be generated, [height, width, colors].
      batch_norm_cls: Class for batch normalization or None.
      spectral_norm: If True use spectral normalization for all weights.
    """
    super(AbstractGenerator, self).__init__(name=name)
    self._name = name
    self._image_shape = image_shape
    self._batch_norm_cls = batch_norm_cls
    self._spectral_norm = spectral_norm

  def batch_norm(self, ch, **kwargs):
    if self._batch_norm_cls is None:
      return dg.Sequential()
    args = kwargs.copy()
    args["ch"] = ch
    if "use_sn" not in args:
      args["use_sn"] = self._spectral_norm
    return utils.call_with_accepted_args(self._batch_norm_cls, **args)

  @abc.abstractmethod
  def forward(self, z, y=None):
    """Forward for the given inputs.
    Args:
      z: `Tensor` of shape [batch_size, z_dim] with latent code.
      y: `Tensor` of shape [batch_size, num_classes] with one hot encoded
        labels.
    Returns:
      Generated images of shape [batch_size] + self.image_shape.
    """


@gin.configurable("D", blacklist=["name"])
class AbstractDiscriminator(Module):
  """Interface for discriminator architectures."""

  def __init__(self,
               name="discriminator",
               image_shape=None,
               batch_norm_cls=None,
               layer_norm=False,
               spectral_norm=False):
    super(AbstractDiscriminator, self).__init__(name=name)
    self._name = name
    self._image_shape = image_shape
    self._batch_norm_cls = batch_norm_cls
    self._layer_norm = layer_norm
    self._spectral_norm = spectral_norm

  def batch_norm(self, ch, **kwargs):
    if self._batch_norm_cls is None:
      return dg.Sequential()
    args = kwargs.copy()
    args["ch"] = ch
    if "use_sn" not in args:
      args["use_sn"] = self._spectral_norm
    return utils.call_with_accepted_args(self._batch_norm_cls, **args)

  @abc.abstractmethod
  def forward(self, x, y=None):
    """Forward for the given inputs.
    Args:
      x: `Tensor` of shape [batch_size, ?, ?, ?] with real or fake images.
      y: `Tensor` of shape [batch_size, num_classes] with one hot encoded
        labels.
    Returns:
      Tuple of 3 Tensors, the final prediction of the discriminator, the logits
      before the final output activation function and logits form the second
      last layer.
    """