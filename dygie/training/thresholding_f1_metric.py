import logging
from overrides import overrides
import numpy as np
import torch
from allennlp.training.metrics.metric import Metric

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

import numpy.ma as ma

# @Metric.register("threshold_f1")
class BinaryThresholdF1(Metric):
    """
    F1 measure optimised for validation set
    """

    def __init__(self, bins=100) -> None:
        """Args:
            bins: number of threshold bins for the fast computation of AP
        """
        self._n_bins = bins
        self.bins = np.linspace(0.001, 0.999, bins)
        self.matched_counts = np.array([0] * self._n_bins)
        self.predicted_counts = np.array([0] * self._n_bins)
        self.total_counts = np.array([0] * self._n_bins)

    def __call__(self,
                 predictions: torch.Tensor,
                 gold_labels: torch.Tensor):
        """
        Parameters
        ----------
        predictions : ``torch.Tensor``, required.
            A tensor of predictions of shape (batch_size, ..., num_classes).
        gold_labels : ``torch.Tensor``, required.
            A tensor of zeros and ones of shape (batch_size, ..., num_classes). It must be the same
            shape as the ``predictions`` tensor.
        """
        # Get the data from the Variables to avoid GPU memory leak
        predictions, gold_labels = self.unwrap_to_tensors(predictions, gold_labels)

        pred = predictions.numpy().ravel().astype(float)
        gold = gold_labels.numpy().ravel().astype(int)

        assert np.all(pred <= 1.0), breakpoint()
        assert np.all(gold <= 1.0), breakpoint()
        assert np.all(pred >= 0.0), breakpoint()
        assert np.all(gold >= 0.0), breakpoint()

        self.total_counts += gold[:, None].sum(0)
        binned_predictions = (pred[:, None] > self.bins).astype(int)

        self.predicted_counts += binned_predictions.sum(0)
        self.matched_counts += (binned_predictions * gold[:, None]).sum(0)

    def get_metric(self, reset: bool = False):
        """
        Returns average precision.

        If reset=False, returns the fast AP.
        If reset=True, returns accurate AP, logs difference ebtween accurate and fast AP and
                       logs a list of points on the precision-recall curve.

        """
        precision = _prf_divide(self.matched_counts, self.predicted_counts)
        recall = _prf_divide(self.matched_counts, self.total_counts)
        f1 = _prf_divide(2*precision*recall , (precision + recall))

        best_idx = np.argmin(np.abs(precision - recall))
        best_threshold = self.bins[best_idx]

        metrics = {
            "total_gold" : float(self.total_counts[best_idx]),
            "total_predicted" : float(self.predicted_counts[best_idx]),
            "total_matched" : float(self.matched_counts[best_idx])
        }

        if reset :
            self.reset()

        metrics.update({
            "precision" : float(precision[best_idx])*100,
            "recall" : float(recall[best_idx])*100,
            "f1" : float(f1[best_idx])*100,
            "threshold" : best_threshold,
        })
        
        return metrics

    @overrides
    def reset(self):
        self.matched_counts = np.array([0] * self._n_bins)
        self.predicted_counts = np.array([0] * self._n_bins)
        self.total_counts = np.array([0] * self._n_bins)

def _prf_divide(numerator, denominator):
    """Performs division and handles divide-by-zero.
    On zero-division, sets the corresponding result elements to zero.
    """
    result = numerator / denominator
    mask = denominator == 0.0
    return ma.array(result, mask=mask)