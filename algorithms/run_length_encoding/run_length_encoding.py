# -*- coding: utf-8 -*-

"""
/***************************************************************************
 RunLengthEncoding
                                 A QGIS plugin
 Creates Run-length Encoding
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-03-10
        copyright            : (C) 2021 by gwolf
        email                : grey_wolf.88@mail.ru
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'gwolf'
__date__ = '2021-03-10'
__copyright__ = '(C) 2021 by gwolf'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
from typing import Dict, Any, Union, Optional

import processing
from processing.modeler.ModelerDialog import ModelerDialog
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource, QgsFeatureSource, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterFeatureSink, QgsProcessingContext, QgsProcessingFeedback,
                       QgsProcessingParameterCrs, QgsProcessingParameterNumber,
                       QgsProcessingMultiStepFeedback, QgsCoordinateReferenceSystem, QgsProcessingUtils, QgsExpression,
                       QgsFeatureRequest, QgsFeature, QgsVectorLayer, QgsField,
                       QgsRasterLayer, QgsFields, QgsProcessingParameterRasterLayer,
                       QgsProcessingFeatureSourceDefinition, QgsProject, QgsMapLayerStore, QgsRectangle, QgsPoint,
                       QgsProcessingParameterBoolean)

from ...modules.optionParser import parseOptions
from ...modules.rle_functions import convertRasterToNumpyArray, rle_encode, save_raster

# загружаем настройки по умолчанию
options = parseOptions(__file__)


class RunLengthEncoding(QgsProcessingAlgorithm):
    SAMPLES = 'SAMPLES'  # Входной слой
    MOSAIC = 'MOSAIC'  # слой растровой мозаики
    CRS = 'CRS'  # Система координат
    HORRESOLUTION = 'HORRESOLUTION'  # Горизонтальное разрешение в единицах проекции
    VERTRESOLUTION = 'VERTRESOLUTION'  # Вертикальное разрешение в единицах проекции
    WIDTH = 'WIDTH'  # Ширина тайла в пикселях
    HEIGHT = 'HEIGHT'  # Высота тайла в пикселях
    INTERSECTION = 'INTERSECTION'  # Слой SAMPLES с образцами, распределенными по сетке тайлов GRID
    SAVEONESAMPLE = 'SAVEONESAMPLE'
    GRID = 'GRID'  # Сетка тайлов
    RLE = 'RLE'  # Описание RLE
    FOLDER = 'FOLDER'  # Папка в которую будут сохраняться порезанная мозаика

    def __init__(self, plugin_dir: str) -> None:
        self.__plugin_dir = plugin_dir

        # Загружаем модель для генерации грида из файла
        self.grid_model = ModelerDialog()
        self.grid_model.loadModel(os.path.join(self.__plugin_dir, r"qgis_models", "grid.model3"))

        # Загружаем модель для генерации слоя intersection из файла
        self.intersection_model = ModelerDialog()
        self.intersection_model.loadModel(os.path.join(self.__plugin_dir, r"qgis_models", "intersection.model3"))

        super().__init__()

    def initAlgorithm(self, config: Dict[str, Any]) -> None:

        # Описываем входные параметры

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                name=self.SAMPLES,
                description='Input layer',
                types=[QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                name=self.MOSAIC,
                description='Rater mosaic layer',
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterCrs(
                name=self.CRS,
                description='CRS',
                defaultValue=options.get(self.CRS, None)
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                name=self.HORRESOLUTION,
                description='Horizontal resolution',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=options.get(self.HORRESOLUTION, None)
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                name=self.VERTRESOLUTION,
                description='Vertical resolution',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=options.get(self.VERTRESOLUTION, None)
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                name=self.WIDTH,
                description='Width (pixel)',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=options.get(self.WIDTH, None)
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                name=self.HEIGHT,
                description='Height (pixel)',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=options.get(self.HEIGHT, None)
            )
        )

        self.addParameter(
            QgsProcessingParameterFolderDestination(
                name=self.FOLDER,
                description='Output folder for mosail tiles',
                defaultValue=options.get(self.FOLDER, None),
                optional=True
            )
        )

        self.addParameter(QgsProcessingParameterBoolean(
            name=self.SAVEONESAMPLE,
            description='Save one sample as raster',
            defaultValue=options.get(self.SAVEONESAMPLE, None),
            optional=False
        ))

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                name=self.INTERSECTION,
                description='Samples per tiles',
                createByDefault=True,
                supportsAppend=True,
                defaultValue='TEMPORARY_OUTPUT'
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                name=self.GRID,
                description='Grid layer',
                createByDefault=True,
                supportsAppend=True,
                defaultValue='TEMPORARY_OUTPUT'
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                name=self.RLE,
                description='RLE',
                createByDefault=True,
                supportsAppend=True,
                defaultValue='TEMPORARY_OUTPUT'
            )
        )

    def processAlgorithm(self, parameters: Dict[str, Any],
                         context: QgsProcessingContext,
                         feedback: QgsProcessingFeedback) -> Union[dict, Dict[str, Any]]:

        # Словарь в котором будут сохраняться результаты работы алгоритма
        result = dict()

        # Получаем переданные на вход параметры
        source: QgsFeatureSource = self.parameterAsSource(parameters, self.SAMPLES, context)

        if self.MOSAIC in parameters and parameters[self.MOSAIC]:
            whole_mosaic: Optional[QgsRasterLayer] = self.parameterAsRasterLayer(parameters, self.MOSAIC, context)
        else:
            whole_mosaic = None

        horresolution: float = self.parameterAsDouble(parameters, self.HORRESOLUTION, context)
        vertresolution: float = self.parameterAsDouble(parameters, self.VERTRESOLUTION, context)
        width: int = self.parameterAsInt(parameters, self.WIDTH, context)
        height: int = self.parameterAsInt(parameters, self.HEIGHT, context)
        dest_crs: QgsCoordinateReferenceSystem = self.parameterAsCrs(parameters, self.CRS, context)

        if self.FOLDER in parameters and parameters[self.FOLDER]:
            folder: Optional[str] = self.parameterAsFileOutput(parameters, self.FOLDER, context)
        else:
            folder = None

        saveonesample: bool = self.parameterAsBoolean(parameters, self.SAVEONESAMPLE, context)

        step = 0
        model_feedback = QgsProcessingMultiStepFeedback(4, feedback)
        if feedback.isCanceled():
            return result

        # Запускаем загруженный из файла алгоритм, который создает слои INTERSECTION и GRID
        temp_grid_id = processing.run(self.grid_model.model(),
                                      {'CRS': dest_crs,
                                       'SAMPLES': parameters[self.SAMPLES],
                                       'HORRESOLUTION': horresolution,
                                       'VERTRESOLUTION': vertresolution,
                                       'HEIGHT': height,
                                       'WIDTH': width,
                                       'VERBOSE_LOG': True,
                                       'native:renametablefield_1:{}'.format(self.GRID): 'TEMPORARY_OUTPUT'},
                                      context=context,
                                      feedback=model_feedback,
                                      is_child_algorithm=True)['native:renametablefield_1:{}'.format(self.GRID)]

        step += 1
        model_feedback.setCurrentStep(step)
        if feedback.isCanceled():
            return result

        temp_grid: QgsVectorLayer = context.takeResultLayer(temp_grid_id)

        if whole_mosaic and folder:
            # Извлекаем екстент из мозаики и любую (первую) точку из грида, чтобы по ним вычислить смещение
            mosaic_extent: QgsRectangle = whole_mosaic.extent()
            first_point: QgsPoint = temp_grid.getFeatures().__next__().geometry().vertices().__next__()

            # вычисляем смещения и двигаем грид
            translated_grid_id = processing.run("native:translategeometry",
                                                {
                                                    'INPUT': temp_grid,
                                                    'DELTA_X': (
                                                                           mosaic_extent.xMaximum() - first_point.x()) % horresolution,
                                                    'DELTA_Y': (
                                                                           mosaic_extent.yMaximum() - first_point.y()) % vertresolution,
                                                    'DELTA_Z': 0,
                                                    'DELTA_M': 0,
                                                    'OUTPUT': 'TEMPORARY_OUTPUT'
                                                },
                                                context=context,
                                                feedback=model_feedback,
                                                is_child_algorithm=True)['OUTPUT']

            translated_grid: QgsVectorLayer = context.takeResultLayer(translated_grid_id)
        else:
            translated_grid_id = temp_grid_id
            translated_grid = temp_grid

        step += 1
        model_feedback.setCurrentStep(step)
        if feedback.isCanceled():
            return result

        temp_intersection_id = processing.run(self.intersection_model.model(),
                                              {'CRS': dest_crs,
                                               'SAMPLES': parameters[self.SAMPLES],
                                               'GRID': translated_grid,
                                               'VERBOSE_LOG': True,
                                               'native:intersection_1:{}'.format(
                                                   self.INTERSECTION): 'TEMPORARY_OUTPUT'},
                                              context=context,
                                              feedback=model_feedback,
                                              is_child_algorithm=True)[
            'native:intersection_1:{}'.format(self.INTERSECTION)]

        temp_intersection: QgsVectorLayer = context.takeResultLayer(temp_intersection_id)

        # Создаем выходные слои, записываем в них features и сохраняем с словарь результатов result
        (intersection, intersection_id) = self.parameterAsSink(parameters, self.INTERSECTION,
                                                               context, temp_intersection.fields(),
                                                               temp_intersection.wkbType(),
                                                               temp_intersection.sourceCrs())

        (grid, grid_id) = self.parameterAsSink(parameters, self.GRID,
                                               context, translated_grid.fields(), translated_grid.wkbType(),
                                               translated_grid.sourceCrs())

        intersection.addFeatures(temp_intersection.getFeatures())
        grid.addFeatures(translated_grid.getFeatures())

        result.update({
            self.INTERSECTION: intersection_id,
            self.GRID: grid_id
        })

        step += 1
        model_feedback.setCurrentStep(step)
        if feedback.isCanceled():
            return result

        # Поля для выходного слоя RLE
        rle_fields = QgsFields()
        rle_fields.append(QgsField("Image_Label", QVariant.String))
        rle_fields.append(QgsField("EncodedPixels", QVariant.String))

        # Выходной слой RLE
        (rle, rle_id) = self.parameterAsSink(parameters, self.RLE,
                                             context, rle_fields, translated_grid.wkbType(),
                                             QgsCoordinateReferenceSystem())
        rle: QgsFeatureSink

        store: QgsMapLayerStore = QgsProject.instance().layerStore()

        # Добавляем слои в хранилище слоев проекта, чтобы их id видел QgsProcessingFeatureSourceDefinition
        store.addMapLayer(temp_intersection)
        store.addMapLayer(translated_grid)

        # Индикатор для сохранения одного растра с sample
        first = True

        # Цикл по каждому тайлу из GRID
        for current, tile_feat in enumerate(translated_grid.getFeatures()):

            tile_feat: QgsFeature

            if feedback.isCanceled():
                return result

            # для каждого тайла создаем запрос по которому будут запрошены соответствующие feature из INTERSECTION
            expression = QgsExpression().createFieldEqualityExpression("tile_id", tile_feat["tile_id"])
            request = QgsFeatureRequest()
            request.setFilterExpression(expression)

            # Цикл по всем feature в INTERSECTION
            for samle_feat in temp_intersection.getFeatures(request):
                samle_feat: QgsFeature

                # выделяем в слое INTERSECTION текущую feature, чтобы только ее передать в алгоритм обрезки растра
                temp_intersection.selectByIds([samle_feat.id()])

                # Превращаем текущую feature из INTERSECTION в растр, экстент растра задаем по текущему тайлу
                bin_raster = processing.run("gdal:rasterize",
                                            {'BURN': 1,
                                             'DATA_TYPE': 0,
                                             'EXTENT': tile_feat.geometry().boundingBox(),
                                             'EXTRA': '',
                                             'FIELD': '',
                                             'HEIGHT': vertresolution,
                                             'INIT': None,
                                             'INPUT': QgsProcessingFeatureSourceDefinition(temp_intersection.id(),
                                                                                           selectedFeaturesOnly=True),
                                             'INVERT': False,
                                             'NODATA': 0,
                                             'OPTIONS': 'NBITS=1',
                                             'OUTPUT': 'TEMPORARY_OUTPUT',
                                             'UNITS': 1,
                                             'WIDTH': horresolution},
                                            context=context,
                                            feedback=model_feedback,
                                            is_child_algorithm=True)['OUTPUT']

                # Получаем результат работы алгоритма в виде растра
                bin_raster: QgsRasterLayer = QgsProcessingUtils.mapLayerFromString(bin_raster, context)

                if first and folder and saveonesample:
                    first = False
                    save_raster(bin_raster, folder, str(tile_feat["tile_id"]).zfill(5) + '_sample.tif')

                # Получаем строку RLE
                raster_rle_string = rle_encode(convertRasterToNumpyArray(bin_raster))

                # Записываем строку с описанием RLE в слой RLE
                feat = QgsFeature(rle_fields)
                feat["Image_Label"] = tile_feat["tile_id"]
                feat["EncodedPixels"] = raster_rle_string
                rle.addFeatures([feat])

                if feedback.isCanceled():
                    return result

            # если указаны мозаика и выходная папка, то обрезаем мозаику по текущему тайлу GRID
            if whole_mosaic and folder:

                if feedback.isCanceled():
                    return result

                # выделяем в слое GRID текущий тайл, чтобы только его передать в алгоритм обрезки растра
                translated_grid.selectByIds([tile_feat.id()])

                mosaic_tile_temp_raster = processing.run("gdal:cliprasterbymasklayer",
                                                         {'ALPHA_BAND': False,
                                                          'CROP_TO_CUTLINE': True,
                                                          'DATA_TYPE': 0,
                                                          'EXTRA': '',
                                                          'INPUT': whole_mosaic,
                                                          'KEEP_RESOLUTION': False,
                                                          # 'MASK': single_grid,
                                                          'MASK': QgsProcessingFeatureSourceDefinition(
                                                              translated_grid.id(),
                                                              selectedFeaturesOnly=True),
                                                          'MULTITHREADING': False,
                                                          'NODATA': None,
                                                          'OPTIONS': '',
                                                          # 'OUTPUT': 'TEMPORARY_OUTPUT',
                                                          'OUTPUT': os.path.join(folder,
                                                                                 str(tile_feat["tile_id"]).zfill(
                                                                                     5)) + '.tif',
                                                          'SET_RESOLUTION': True,
                                                          'SOURCE_CRS': None,
                                                          'TARGET_CRS': None,
                                                          'X_RESOLUTION': abs(whole_mosaic.rasterUnitsPerPixelX()),
                                                          'Y_RESOLUTION': abs(whole_mosaic.rasterUnitsPerPixelX())},
                                                         context=context,
                                                         feedback=model_feedback,
                                                         is_child_algorithm=True)["OUTPUT"]

                if feedback.isCanceled():
                    return result

        store.removeMapLayer(temp_intersection)
        store.removeMapLayer(translated_grid)

        step += 1
        model_feedback.setCurrentStep(step)
        if feedback.isCanceled():
            return result

        result.update({self.RLE: rle_id})
        return result

    def name(self) -> str:
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Run-length Encoding'

    def displayName(self) -> str:
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.name()

    def group(self) -> str:
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.groupId()

    def groupId(self) -> str:
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Vasya'

    # def tr(self, string):
    #     return QCoreApplication.translate('Processing', string)

    def createInstance(self) -> QgsProcessingAlgorithm:
        return RunLengthEncoding(self.__plugin_dir)
