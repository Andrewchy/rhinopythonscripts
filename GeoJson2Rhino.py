"""
Allows for the translation of GeoJSON data to Rhino objects

I don't think GeoJSON format supports 3D, unfortunately, so I plan to add some
3d functionality in which one could designate z attribute column names.

The GeoJSON Format Specification can be found here:
    http://geojson.org/geojson-spec.html

The RhinoCommon SDK (where all the Rhino.Geometry objects are documented) is
here:
    http://www.rhino3d.com/5/rhinocommon/

Example of Use:
    >>> import GeoJson2Rhino as geoj
    >>> myGeoJson = '''
{ "type": "FeatureCollection",
  "features": [
    { "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
      "properties": {"prop0": "value0"}
      },
    { "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [102.0, 0.0], [103.0, 1.0], [104.0, 0.0], [105.0, 1.0]
          ]
        },
      "properties": {
        "prop0": "value0",
        "prop1": 0.0
        }
      },
    { "type": "Feature",
       "geometry": {
         "type": "Polygon",
         "coordinates": [
           [ [100.0, 0.0], [101.0, 0.0], [101.0, 1.0],
             [100.0, 1.0], [100.0, 0.0] ]
           ]
       },
       "properties": {
         "prop0": "value0",
         "prop1": {"this": "that"}
         }
       }
     ]
   }'''
   >>> guidList = geoj.load(myGeoJson) #stores guids of new rhino objects

"""

# Import standard library modules
import json

# Import Rhino modules
import Rhino
from Rhino.Geometry import *
from scriptcontext import doc

# import .NET libraries
import System


def addRhinoLayer(layerName, layerColor=System.Drawing.Color.Black):
    """Creates a Layer in Rhino using a name and optional color. Returns the
    index of the layer requested. If the layer
    already exists, the color is updated and no new layer is created."""
    docLyrs = doc.Layers
    layerIndex = docLyrs.Find(layerName, True)
    if layerIndex == -1:
        layerIndex = docLyrs.Add(layerName,layerColor)
    else: # it exists
        layer = docLyrs[layerIndex] # so get it
        if layer.Color != layerColor: # if it has a different color
            layer.Color = layerColor # reset the color
    return layerIndex

def PointToRhinoPoint(coordinates):
    x, y = coordinates[0], coordinates[1]
    z = 0.0
    return Point3d(x, y, z)

def MultiPointToRhinoPoint(coordinates):
    rhPointList = []
    for pair in coordinates:
        rhPointList.append(PointToRhinoPoint(pair))
    return rhPointList

def LineStringToRhinoCurve(coordinates):
    rhPoints = MultiPointToRhinoPoint(coordinates)
    return Curve.CreateControlPointCurve(rhPoints, 1)

def MultiLineStringToRhinoCurve(coordinates):
    rhCurveList = []
    for lineString in coordinates:
        rhCurveList.append(LineStringToRhinoCurve(lineString))
    return rhCurveList

def PolygonToRhinoCurve(coordinates):
    # each ring is a separate list of coordinates
    ringList = []
    for ring in coordinates:
        ringList.append(LineStringToRhinoCurve(ring))
    return ringList

def MultiPolygonToRhinoCurve(coordinates):
    polygonList = []
    for polygon in coordinates:
        polygonList.append(PolygonToRhinoCurve(polygon))
    return polygonList

def GeometryCollectionToParser(geometries):
    pass # I need to figure this one out still

def addPoint(rhPoint, objAtt):
    return doc.Objects.AddPoint(rhPoint, objAtt)

def addPoints(rhPoints, objAtt):
    return doc.Objects.AddPoints(rhPoints, objAtt)

def addCurve(rhCurve, objAtt):
    return doc.Objects.AddCurve(rhCurve, objAtt)

def addCurves(rhCurves, objAtt):
    guidList = []
    for curve in rhCurves:
        guidList.append(addCurve(curve, objAtt))
    return guidList

def addPolygon(ringList, objAtt):
    # for now this just makes curves
    # but maybe it should make TrimmedSrfs
    # or should group the rings
    return addCurves(ringList, objAtt)

def addPolygons(polygonList, objAtt):
    guidList = []
    for polygon in polygonList:
        # !! Extending the guid list !!!
        guidList.extend(addPolygon(polygon, objAtt))
    return guidList

geoJsonGeometryMap = {
        'Point':(PointToRhinoPoint, addPoint),
        'MultiPoint':(MultiPointToRhinoPoint, addPoints),
        'LineString':(LineStringToRhinoCurve, addCurve),
        'MultiLineString':(MultiLineStringToRhinoCurve, addCurves),
        'Polygon':(PolygonToRhinoCurve, addPolygon),
        'MultiPolygon':(MultiPolygonToRhinoCurve, addPolygons),
        'GeometryCollection':(GeometryCollectionToParser),
        }


def processGeoJson(parsedGeoJson,
         destinationLayer=None,
         destinationLayerColor=System.Drawing.Color.Black):

    # get the features
    jsonFeatures = parsedGeoJson['features']
    guidResults = []

    for jsonFeature in jsonFeatures: # for each feature

        # set up object attributes
        att = Rhino.DocObjects.ObjectAttributes()
        # setup layer if requested
        if destinationLayer != None:
            att.LayerIndex = addRhinoLayer(destinationLayer,
                                           destinationLayerColor)

        # deal with the properties
        if jsonFeature['properties']:
            properties = jsonFeature['properties']
            for key in properties:
                att.SetUserString(key, str(properties[key]))

        # deal with the geometry
        geom = jsonFeature['geometry']
        geomType = geom['type'] # this will return a mappable string
        coordinates = geom['coordinates']

        # translate the coordinates to Rhino.Geometry objects
        rhFeature = geoJsonGeometryMap[geomType][0](coordinates)

        # return the GUID(s) for the feature
        guidResults.append(geoJsonGeometryMap[geomType][1](rhFeature, att))

    # return all the guids
    return guidResults

def load(rawGeoJsonData,
         destinationLayer=None,
         destinationLayerColor=System.Drawing.Color.Black):
    # parse the data
    geoJson = json.loads(rawGeoJsonData)
    return processGeoJson(geoJson)

def loadLayers(rawJsonData):
    """Loads a Json object that contains a set of GeoJSON objects in 'layers',
    of the form:
        {"layername":{"type":"FeatureCollection","features":[...]},
         "layername2":{"type":"FeatureCollection","features":[...]},
         }
    For each layer name, it creates a separate Rhino Layer with the
    corresponding name."""

    # this needs a sub function that gets the number of keys and then creates a
    # different color for each key
    if type(rawJsonData) == str:
        layersJson = json.loads(rawJsonData)
    elif type(rawJsonData) == dict:
        layersJson = rawJsonData

    # make a list to hold all the guid results
    allResults = []

    for layerKey in layersJson: # for each layer
        layerResults = processGeoJson(layersJson[layerKey],
                destinationLayer=layerKey)
        allResults.append(layerResults)

    return allResults















