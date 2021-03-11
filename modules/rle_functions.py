import numpy as np
from qgis.core import QgsRasterLayer, QgsRasterDataProvider


# Функция конвертации растра в массив numpy
def convertRasterToNumpyArray(lyr: QgsRasterLayer) -> np.array:
    provider: QgsRasterDataProvider = lyr.dataProvider()

    block = provider.block(1, lyr.extent(), lyr.width(), lyr.height())
    arr = np.zeros((lyr.height(), lyr.width()), dtype=int)

    for i in range(lyr.width()):
        for j in range(lyr.height()):
            arr[i, j] = block.value(i, j)

    return arr

# Функция генерации строки RLE из массива numpy
def rle_encode(img: np.array) -> str:
    '''
    img: numpy array, 1 - mask, 0 - background
    Returns run length as string formated
    '''
    pixels = img.flatten()
    pixels = np.concatenate([[0], pixels, [0]])
    runs = np.where(pixels[1:] != pixels[:-1])[0] + 1
    runs[1::2] -= runs[::2]
    return ' '.join(str(x) for x in runs)