import abc
import tensorflow as tf

import network.network_base as network_base

__author__ = 'garrett_local'


class LossCorrectionNetwork(network_base.NetworkBase):
    def __init__(self, loss_type='cross_entropy', trainable=True,
                 do_summarizing=False, transition_mat=None):
        """
        Initialize all the placeholders.
        :param loss_type: basestring, indicating which type of loss is used,
                    including cross_entropy, backward, backward_t, forward,
                    forward_t.
        :param transition_mat: Numpy mat for transition matrix which describes
                    label noise.
        :param trainable: if the network is trainable.
        """
        network_base.NetworkBase.__init__(self, trainable)
        if loss_type != 'cross_entropy' and transition_mat is None:
            raise ValueError('transition_mat must be set when using loss '
                             'correction.')
        self.loss_type = loss_type
        self.do_summarizing = do_summarizing
        self.x = None
        self.y = None
        self.keep_prob = None
        self.transition_mat = transition_mat
        self.transition_tensor = None

    @abc.abstractmethod
    def get_placeholder_x(self):
        """
        An abstract function must be implemented. This should return a
        placeholder for feature feeding.
        :return: a placeholder for feature feeding.
        """

    @abc.abstractmethod
    def get_placeholder_y(self):
        """
        An abstract function must be implemented. This should return a
        placeholder for label feeding. y should strictly be of shape
        [batch_size, classes_number].
        :return: a placeholder for label feeding.
        """

    def build_loss(self):
        """
        Build loss. Loss correction will be performed here, if self.loss_type
        is set appropriately.
        :return: None.
        """
        assert hasattr(self, 'transition_mat'), ('transition_mat not exist,'
                                                 'maybe because that '
                                                 'LossCorrectionNetwork.__init__()'
                                                 'is not called by its subclass.')
        with tf.compat.v1.variable_scope('input'):
            if ((self.loss_type == 'backward') or
                    (self.loss_type == 'backward_t') or
                    (self.loss_type == 'forward') or
                    (self.loss_type == 'forward_t')):
                self.transition_tensor = tf.Variable(
                    self.transition_mat,
                    dtype=tf.float32,
                    trainable=False
                )
                self.layers['t'] = self.transition_tensor

        with tf.name_scope('loss'):
            if self.loss_type == 'cross_entropy':
                loss = -tf.reduce_mean(
                    tf.math.reduce_sum(
                        self.get_placeholder_y() * tf.math.log(self.get_tensor_prediction()+ 10e-12),
                        axis=1
                    )
                )
                self.layers['loss'] = loss
            elif self.loss_type == 'backward':
                y_trans = tf.transpose(self.get_placeholder_y(), perm=[1,0])
                t_inv = tf.linalg.inv(self.get_output('t'))
                t_inv_trans = tf.transpose(t_inv, perm=[1,0])
                l_orig = -tf.math.log(self.get_tensor_prediction() + 10e-12)
                l_backward_full = tf.matmul(l_orig, t_inv_trans)
                loss = tf.reduce_mean(
                    tf.math.reduce_sum(
                        tf.linalg.band_part(
                            tf.matmul(l_backward_full, y_trans),
                            0,
                            0
                        ),
                        axis=1
                    )
                )
                self.layers['loss'] = loss
            elif self.loss_type == 'forward':
                corrected_pred = tf.matmul(self.get_tensor_prediction(),
                                           self.get_output('t'))
                loss = -tf.reduce_mean(tf.math.reduce_sum(self.get_placeholder_y() *
                                                     tf.math.log(corrected_pred
                                                            + 10e-12),
                                                     axis=1))
                self.layers['corrected_pred'] = corrected_pred
                self.layers['loss'] = loss
            else:
                raise RuntimeError('Incorrect loss function.')
        self.add_summary(loss, name='loss')