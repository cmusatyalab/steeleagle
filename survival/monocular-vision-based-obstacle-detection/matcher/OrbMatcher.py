import cv2

from utils.timer import timing

MAX_FEATURES = 500
ORB = cv2.ORB_create(MAX_FEATURES)

SIMPLE_DESCRIPTOR_MATCHER = cv2.DescriptorMatcher_create(cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING)

# Makes sure matches match both ways: min(desc_a, desc_b)
CROSS_CHECK_DESCRIPTOR_MATCHER = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


@timing
def get_matches(descriptor_a, descriptor_b, max_distance=30):
    """
    Calculates matches between descriptors a and b.
    Only return matches with a maximum distance of max_distance.
    """
    matches = CROSS_CHECK_DESCRIPTOR_MATCHER.match(descriptor_a, descriptor_b, None)
    filtered_matches = list(filter(lambda m: m.distance <= max_distance, matches))
    return filtered_matches


@timing
def average_descriptor_distance(descriptor_a, descriptor_b) -> float:
    """
    Calculates the average distance between matched keypoints.
    The result is scaled so that is comparable between SIFT, SURF and ORB.
    This way it returns a number between 0 and 1 for each matcher.
    100 is returned in case less than 10% of the keypoints match to signal "no match".
    """
    matches = SIMPLE_DESCRIPTOR_MATCHER.match(descriptor_a, descriptor_b, None)

    avg_number_of_descriptors = (len(descriptor_a) + len(descriptor_b)) / 2
    percent_of_matches = len(matches) / avg_number_of_descriptors
    if percent_of_matches < 0.1:
        return 100  # Less than 10% matches -> No Similarity
    # sum distances
    total_distance = sum([d.distance for d in matches])
    # divide by number of matches
    avg_distance = total_distance / len(matches) / 100
    return avg_distance


@timing
def get_keypoints_and_descriptors_for_object(grayscale_image, mask):
    """
    Detect ORB features and compute descriptors.
    :param grayscale_image: whole image as grayscale
    :param mask: search mask that restricts the area in which to search for keypoints
    :return:
    """
    return ORB.detectAndCompute(grayscale_image, mask)
