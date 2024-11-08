Task {
    Detect tri {
        way_points: <Triangle>,
        gimbal_pitch: -20.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco,
        hsv_lower_bound: (30, 100, 100),
        hsv_upper_bound: (50, 255, 255)
    }
    Detect rect {
        way_points: <Rectangle>,
        gimbal_pitch: -20.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco,
        hsv_lower_bound: (30, 100, 100),
        hsv_upper_bound: (50, 255, 255)
    }
}
Mission {
    Start tri
    Transition (timeout(10)) tri -> rect
    Transition (done) rect -> tri
}
