from typing import Tuple

import numpy as np
from filterpy.common import Q_discrete_white_noise
from filterpy.kalman import KalmanFilter

import Constants

MAX_UNCERTAINTY = Constants.INPUT_DIMENSIONS[0] / 5


class KalmanTracker:
    """
    Kalman Filter of the second degree
    """

    def __init__(self, initial_pos_x=0, initial_pos_y=0):
        self.kf = KalmanFilter(dim_x=6, dim_z=2)

        self.kf.x = np.array([[initial_pos_x, initial_pos_y, 0.0, 0.0, 0.0, 0.0]], np.float32).T  # state

        dt = 1.0
        self.kf.F = np.array(
            [
                [1.0, 0.0, dt, 0.0, dt ** 2 / 2, 0.0],  # pos.x, pos.y, vel.x, vel.y, acc.x, acc.y
                [0.0, 1.0, 0.0, dt, 0.0, dt ** 2 / 2],
                [0.0, 0.0, 1.0, 0.0, dt, 0.0],
                [0.0, 0.0, 0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            ]
        )  # state transition matrix

        self.kf.H = np.array([[1., 0, 0, 0, 0, 0],  # pos.x, pos.y, vel.x, vel.y, acc.x, acc.y
                              [0., 1, 0, 0, 0, 0]])  # Measurement function

        self.kf.P *= Constants.INPUT_DIMENSIONS[0] / 5  # covariance matrix
        self.kf.R = np.eye(2) * Constants.INPUT_DIMENSIONS[0] / 30  # measurement uncertainty
        self.kf.Q = Q_discrete_white_noise(2, dt=dt, var=0.1, block_size=3, order_by_dim=False)  # process uncertainty
        self.last_position_prediction = (0, 0)
        self.last_position_uncertainty = (0, 0)

    def update(self, center_or_none):
        """
        Performs the update > prediction cycle of the Kalman Filter.
        If no new measurement is provided, the update step gets skipped.
        """
        self.last_position_prediction = self.next_position_prediction()
        self.last_position_uncertainty = self.next_position_uncertainty()
        if center_or_none:
            self.kf.update(center_or_none)
        self.kf.predict()

    def next_position_prediction(self) -> Tuple[int, int]:
        """
        This function returns the estimated the position of the object in the next time step
        """
        return int(self.kf.x[0][0]), int(self.kf.x[1][0])

    def current_position_prediction(self) -> Tuple[int, int]:
        """
        This function returns the estimated the position of the object for the current time step (last prediction)
        """
        return self.last_position_prediction

    def next_position_uncertainty(self) -> Tuple[int, int]:
        """
        Returns a tuple with uncertainty in x and y direction
        """
        covariance_matrix = self.kf.P
        covariances = np.diag(covariance_matrix)  # pos.x, pos.y, vel.x, vel.y, acc.x, acc.y
        return int(min(covariances[0], MAX_UNCERTAINTY)), int(min(covariances[1], MAX_UNCERTAINTY))

    def current_position_uncertainty(self) -> Tuple[int, int]:
        """
        Returns a tuple with uncertainty in x and y direction for the current time step (last prediction)
        """
        return self.last_position_uncertainty

    def is_point_in_predicted_area(self, point: Tuple[float, float]) -> bool:
        """
        Tests whether a point is in the area that is span up by the next position prediction plus its uncertainty.
        Uses a rectangle as a simplification/approximation instead of the correct ellipsis.
        """
        x, y = self.next_position_prediction()
        cov_x, cov_y = self.next_position_uncertainty()
        p_x, p_y = point
        return x - cov_x / 2 < p_x < x + cov_x / 2 and y - cov_y / 2 < p_y < y + cov_y / 2
