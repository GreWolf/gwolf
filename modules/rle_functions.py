import numpy as np
from qgis.core import QgsRasterLayer, QgsRasterDataProvider, QgsRasterPipe, QgsRasterFileWriter


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


# функция сохранения растра в файл
def save_raster(rater: QgsRasterLayer, folder: str, name: str) -> None:
    renderer = rater.renderer()
    provider = rater.dataProvider()

    pipe = QgsRasterPipe()
    pipe.set(provider.clone())
    pipe.set(renderer.clone())

    file_writer = QgsRasterFileWriter(np.os.path.join(folder, name))
    file_writer.Mode(1)

    file_writer.writeRaster(pipe, provider.xSize(), provider.ySize(), provider.extent(), provider.crs())
