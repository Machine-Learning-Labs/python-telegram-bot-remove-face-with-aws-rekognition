import boto3

# Cacheable references
rekognition = boto3.client("rekognition")


# Function to call Amazon Rekognition and detect faces in an image
async def detect_faces(image_path):
    """Count the number of faces in one app"""

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    response = rekognition.detect_faces(
        Image={"Bytes": image_bytes}, Attributes=["ALL"]
    )

    return response