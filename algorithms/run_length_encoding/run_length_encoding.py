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
from typing import Dict, Any

import numpy as np

import processing
from processing.modeler.ModelerDialog import ModelerDialog
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink, QgsProcessingContext, QgsProcessingFeedback,
                       QgsProcessingParameterDistance, QgsProcessingParameterCrs, QgsProcessingParameterNumber,
                       QgsProcessingMultiStepFeedback, QgsCoordinateReferenceSystem, QgsProcessingUtils, QgsExpression,
                       QgsFeatureRequest, QgsFeature, QgsVectorLayer, QgsWkbTypes, QgsVectorDataProvider, QgsField,
                       QgsGeometry, QgsRasterLayer, QgsRasterDataProvider, QgsFields)

from ...modules.optionParser import parseOptions

options = parseOptions(__file__)


def convertRasterToNumpyArray(lyr: QgsRasterLayer) -> np.array:
    provider: QgsRasterDataProvider = lyr.dataProvider()

    block = provider.block(1, lyr.extent(), lyr.width(), lyr.height())
    arr = np.zeros((lyr.height(), lyr.width()), dtype=int)

    for i in range(lyr.width()):
        for j in range(lyr.height()):
            arr[i, j] = block.value(i, j)

    return arr


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


class RunLengthEncoding(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    SAMPLES = 'SAMPLES'

    CRS = 'CRS'

    HORRESOLUTION = 'HORRESOLUTION'
    VERTRESOLUTION = 'VERTRESOLUTION'

    WIDTH = 'WIDTH'
    HEIGHT = 'HEIGHT'

    INTERSECTION = 'INTERSECTION'
    GRID = 'GRID'
    RLE = 'RLE'

    def __init__(self, plugin_dir: str):
        self.__plugin_dir = plugin_dir

        self.create_grid = ModelerDialog()
        self.create_grid.loadModel(os.path.join(self.__plugin_dir, r"qgis_models", "create_grid.model3"))

        super().__init__()

    def initAlgorithm(self, config: Dict[str, Any]):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                name=self.SAMPLES,
                description='Input layer',
                types=[QgsProcessing.TypeVectorAnyGeometry]
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
                         feedback: QgsProcessingFeedback):
        """
        Here is where the processing itself takes place.
        """
        result = dict()
        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsSource(parameters, self.SAMPLES, context)
        horresolution: float = self.parameterAsDouble(parameters, self.HORRESOLUTION, context)
        vertresolution: float = self.parameterAsDouble(parameters, self.VERTRESOLUTION, context)
        width: int = self.parameterAsInt(parameters, self.WIDTH, context)
        height: int = self.parameterAsInt(parameters, self.HEIGHT, context)
        dest_crs: QgsCoordinateReferenceSystem = self.parameterAsCrs(parameters, self.CRS, context)

        model_feedback = QgsProcessingMultiStepFeedback(2, feedback)

        if feedback.isCanceled():
            return {}

        proc_result = processing.run(self.create_grid.model(), {
            self.SAMPLES: parameters[self.SAMPLES],
            self.CRS: dest_crs,
            self.HORRESOLUTION: horresolution,
            self.VERTRESOLUTION: vertresolution,
            self.WIDTH: width,
            self.HEIGHT: height,
            'native:intersection_1:{}'.format(self.INTERSECTION): 'TEMPORARY_OUTPUT',
            'native:renametablefield_1:{}'.format(self.GRID): 'TEMPORARY_OUTPUT'
        },
                                     context=context,
                                     feedback=model_feedback,
                                     is_child_algorithm=True)

        print(proc_result)

        temp_intersection: QgsVectorLayer = context.takeResultLayer(
            proc_result['native:intersection_1:{}'.format(self.INTERSECTION)])

        temp_grid: QgsVectorLayer = context.takeResultLayer(
            proc_result['native:renametablefield_1:{}'.format(self.GRID)])


        (intersection, intersection_id) = self.parameterAsSink(parameters, self.INTERSECTION,
                context, temp_intersection.fields(), temp_intersection.wkbType(), temp_intersection.sourceCrs())


        (grid, grid_id) = self.parameterAsSink(parameters, self.GRID,
                                               context, temp_grid.fields(), temp_grid.wkbType(), temp_grid.sourceCrs())

        intersection.addFeatures(temp_intersection.getFeatures())
        grid.addFeatures(temp_grid.getFeatures())

        result.update({self.INTERSECTION: intersection_id, self.GRID: grid_id})

        model_feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return result





        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / temp_grid.featureCount() if temp_grid.featureCount() else 0
        # features = source.getFeatures()

        templayer = QgsVectorLayer('{}?crs={}'.format(QgsWkbTypes.displayString(temp_grid.wkbType()), dest_crs.authid()), 'temp', 'memory')
        data_provider: QgsVectorDataProvider = templayer.dataProvider()

        data_provider.addAttributes(
            [QgsField("sample_id", QVariant.Int),
             QgsField("tile_id", QVariant.Int)])

        print(templayer.crs())
        print(templayer.crs().authid())

        rle_fields = QgsFields()
        rle_fields.append(QgsField("Image_Label", QVariant.String))
        rle_fields.append(QgsField("EncodedPixels", QVariant.String))

        (rle, rle_id) = self.parameterAsSink(parameters, self.RLE,
                                               context, rle_fields, temp_grid.wkbType(), QgsCoordinateReferenceSystem())
        rle: QgsFeatureSink

        for current, tile_feat in enumerate(temp_grid.getFeatures()):
            tile_feat: QgsFeature
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                return result

            # tile_id = tile_feat["tile_id"]

            expression = QgsExpression().createFieldEqualityExpression("tile_id", tile_feat["tile_id"])
            request = QgsFeatureRequest()
            # request.setFlags(QgsFeatureRequest.NoGeometry)
            request.setFilterExpression(expression)

            for samle_feat in temp_intersection.getFeatures(request):
                samle_feat: QgsFeature
                # feat_id = samle_feat.id()

                templayer.startEditing()
                data_provider.addFeatures([samle_feat])
                templayer.commitChanges()
                # geom: QgsGeometry = tile_feat.geometry()

                raster = processing.run("gdal:rasterize",
                               {'BURN': 1,
                                'DATA_TYPE': 0,
                                'EXTENT': tile_feat.geometry().boundingBox(),
                                'EXTRA': '',
                                'FIELD': '',
                                'HEIGHT': vertresolution,
                                'INIT': None,
                                'INPUT': templayer,
                                'INVERT': False,
                                'NODATA': 0,
                                'OPTIONS': 'NBITS=1',
                                'OUTPUT': 'TEMPORARY_OUTPUT',
                                'UNITS': 1,
                                'WIDTH': horresolution},
                               context=context,
                               feedback=model_feedback,
                               is_child_algorithm=True)['OUTPUT']
                print(raster)
                raster = QgsProcessingUtils.mapLayerFromString(raster, context)
                print(raster)

                raster_rle_string = rle_encode(convertRasterToNumpyArray(raster))

                feat = QgsFeature(rle_fields)
                feat["Image_Label"] = tile_feat["tile_id"]
                feat["EncodedPixels"] = raster_rle_string
                rle.addFeatures([feat])

                templayer.startEditing()
                data_provider.deleteFeatures([samle_feat.id()])
                templayer.commitChanges()

            model_feedback.setProgress(int(current * total))

        model_feedback.setCurrentStep(2)


        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
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
