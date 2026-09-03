import os
import json
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2 # type: ignore
from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout # type: ignore
from tensorflow.keras.models import Model # type: ignore
from tensorflow.keras.preprocessing.image import ImageDataGenerator # type: ignore
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint # type: ignore
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input # type: ignore
from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

# 1. Mipangilio (Settings)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
MODEL_SAVE_PATH = os.path.join(BASE_DIR, 'mobilenet_model.h5')
CLASS_INDICES_PATH = os.path.join(BASE_DIR, 'class_indices.json')

IMG_WIDTH, IMG_HEIGHT = 224, 224 # MobileNetV2 default size
BATCH_SIZE = 16
EPOCHS = 20 # Tutaanza na 20 kwa sababu Transfer Learning inajifunza haraka

def create_model(num_classes):
    """
    Kutengeneza model kwa kutumia MobileNetV2 (Transfer Learning)
    """
    # Tunachukua MobileNetV2 iliyofundishwa tayari kwenye picha za 'imagenet'
    # include_top=False inamaanisha tunatoa tabaka la mwisho la utambuzi wa imagenet
    base_model = MobileNetV2(
        weights='imagenet', 
        include_top=False, 
        input_shape=(IMG_WIDTH, IMG_HEIGHT, 3)
    )
    
    # Kufungia base_model isijifunze upya (kuzuia kuharibu kile inachokijua)
    base_model.trainable = False 
    
    # Kuongeza tabaka zetu mpya juu ya MobileNetV2
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.5)(x) # Kuzuia overfitting
    
    # Tabaka la mwisho kulingana na idadi ya mimea yetu
    predictions = Dense(num_classes, activation='softmax')(x)
    
    # Kuunganisha model nzima
    model = Model(inputs=base_model.input, outputs=predictions)
    
    model.compile(optimizer='adam',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])
    return model

def main():
    print("--------------------------------------------------")
    print("Inaanza kuandaa Data Augmentation (Kuzalisha picha)...")
    print("--------------------------------------------------")
    
    # 2. Data Augmentation
    # Hapa tunatumia preprocess_input ya MobileNetV2 badala ya rescale=1./255
    datagen = ImageDataGenerator(
        preprocessing_function=preprocess_input,
        rotation_range=40,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True,
        fill_mode='nearest',
        validation_split=0.2 # Asilimia 20 ya picha itatumika kupima mtihani
    )

    if not os.path.exists(DATASET_DIR):
        print(f"KOSA: Folder la dataset halipo: {DATASET_DIR}")
        return

    # Kusoma picha zote kwenye folder letu
    train_generator = datagen.flow_from_directory(
        DATASET_DIR,
        target_size=(IMG_WIDTH, IMG_HEIGHT),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )

    validation_generator = datagen.flow_from_directory(
        DATASET_DIR,
        target_size=(IMG_WIDTH, IMG_HEIGHT),
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )
    
    # Kuhifadhi majina ya mimea ili tuje kuyatumia kwenye Django
    class_indices = train_generator.class_indices
    with open(CLASS_INDICES_PATH, 'w') as f:
        json.dump(class_indices, f)
    print(f"Majina ya mimea yamehifadhiwa: {class_indices}")

    num_classes = len(class_indices)
    
    if num_classes == 0:
        print("KOSA: Sijaona picha zozote kwenye folder la 'dataset'. Tafadhali weka picha zilizopangwa kwenye mafolder.")
        return

    # 3. Kujenga Model na Kuanza Ku-Train
    model = create_model(num_classes)
    
    # Inaonyesha muundo wa model
    # model.summary() # Unaweza kutoa comment hapa kama unataka kuona muundo mzima
    
    print("\n--------------------------------------------------")
    print("Inaanza kujifunza (Training)... Tafadhali subiri.")
    print("--------------------------------------------------\n")

    # Callbacks: Kusimamisha kama imefikia mwisho wa kujifunza, na ku-save bora
    checkpoint = ModelCheckpoint(MODEL_SAVE_PATH, monitor='val_accuracy', save_best_only=True, verbose=1)
    early_stop = EarlyStopping(monitor='val_accuracy', patience=5, verbose=1)

    # Anza Ku-Train
    history = model.fit(
        train_generator,
        steps_per_epoch=max(1, train_generator.samples // BATCH_SIZE),
        validation_data=validation_generator,
        validation_steps=max(1, validation_generator.samples // BATCH_SIZE),
        epochs=EPOCHS,
        callbacks=[checkpoint, early_stop]
    )

    print("\n--------------------------------------------------")
    print(f"Kazi imekamilika! Model ya MobileNetV2 imehifadhiwa hapa: {MODEL_SAVE_PATH}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
