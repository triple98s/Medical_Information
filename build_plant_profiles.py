"""Build open-set feature profiles for the trained plant classifier.

Run this after training (or after adding images to dataset) before deploying.
It does not retrain the model.
"""
import json
import math
import os

import numpy as np
import tensorflow as tf
from PIL import ImageFile
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input  # type: ignore
from tensorflow.keras.preprocessing.image import ImageDataGenerator  # type: ignore

ImageFile.LOAD_TRUNCATED_IMAGES = True


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
MODEL_PATH = os.path.join(BASE_DIR, 'mobilenet_model.h5')
CLASS_INDICES_PATH = os.path.join(BASE_DIR, 'class_indices.json')
PROFILE_PATH = os.path.join(BASE_DIR, 'plant_feature_profiles.json')
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32


def main():
    if not all(os.path.exists(path) for path in (DATASET_DIR, MODEL_PATH, CLASS_INDICES_PATH)):
        raise SystemExit('dataset, mobilenet_model.h5, and class_indices.json are all required.')

    with open(CLASS_INDICES_PATH, 'r', encoding='utf-8') as file:
        class_indices = json.load(file)

    generator = ImageDataGenerator(preprocessing_function=preprocess_input).flow_from_directory(
        DATASET_DIR, target_size=IMAGE_SIZE, batch_size=BATCH_SIZE,
        class_mode='categorical', shuffle=False,
    )
    if generator.class_indices != class_indices:
        raise SystemExit('Dataset classes do not match class_indices.json. Train the model again first.')

    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    feature_model = tf.keras.Model(inputs=model.input, outputs=model.layers[-2].output)
    features = feature_model.predict(generator, steps=math.ceil(generator.samples / BATCH_SIZE), verbose=1)

    profiles = {}
    for class_name, class_index in class_indices.items():
        class_features = features[generator.classes == class_index]
        if len(class_features) < 2:
            raise SystemExit(f'Class {class_name} needs at least two images.')
        centroid = class_features.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-8
        normalized_features = class_features / (np.linalg.norm(class_features, axis=1, keepdims=True) + 1e-8)
        similarities = normalized_features @ centroid
        # Accept nearly all genuine examples while rejecting distant, unknown images.
        minimum_similarity = max(0.70, float(np.percentile(similarities, 5)) - 0.02)
        profiles[class_name] = {
            'centroid': centroid.astype(float).tolist(),
            'min_similarity': minimum_similarity,
        }

    with open(PROFILE_PATH, 'w', encoding='utf-8') as file:
        json.dump({'profiles': profiles}, file)
    print(f'Created {PROFILE_PATH} with {len(profiles)} class profiles.')


if __name__ == '__main__':
    main()
