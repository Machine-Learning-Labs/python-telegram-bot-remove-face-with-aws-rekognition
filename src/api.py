import boto3

rekognition = boto3.client('rekognition')

# Function to call Amazon Rekognition and detect faces in an image
async def detect_faces(image_path):
    

    with open(image_path, 'rb') as image_file:
        image_bytes = image_file.read()

    response = rekognition.detect_faces(
        Image={
            'Bytes': image_bytes
        },
        Attributes=['ALL']
    )
    
    print(image_path)
    print(len(response['FaceDetails']))
    print(response['FaceDetails'])

    faces = response['FaceDetails']
    
    return faces