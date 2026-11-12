'''Calibration-stage helpers that need no data: split widths, import bookkeeping.'''
import unittest
from unittest import mock

from data_calibration import hvla_data_cal


class ChannelWidths(unittest.TestCase):
  def test_each_spw_is_averaged_to_at_most_16_channels(self):
    with mock.patch('casatools.msmetadata') as msmd:
      msmd.return_value.nspw.return_value = 4
      msmd.return_value.nchan.side_effect = [1, 255, 16, 64]
      self.assertEqual(hvla_data_cal.channel_widths('x.ms'), [1, 16, 1, 4])
      msmd.return_value.close.assert_called_once()


if __name__ == '__main__':
  unittest.main()
