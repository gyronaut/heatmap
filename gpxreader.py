import math
import xml.etree.ElementTree as eltree
import matplotlib.pyplot as plt

# TODO: figure out how to log-in and authenticate before retreiving activity data

# url for json string of every activity in 2020: 
# https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?activityType=running&startDate=2020-01-01

# url for downloading specific garmin gpx track:
# https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/' + activityId
# as seen here: https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-web/63103/show-all-routes-on-the-same-map/930931#930931

def coord2px(lat, lon, zoom):
    x = 256.0/(2.0*math.pi)*(2**zoom)*((lon)*math.pi/180.0 + math.pi)
    y = 256.0/(2.0*math.pi)*(2**zoom)*(math.pi - math.log(math.tan(math.pi/4.0 + (lat*math.pi/180.0)/2.0)))
    return [int(x),int(y)]

# everytime a track crosses to a new tile, need to add two midpoints that connect each tile's segment to the tile edge
def addBoundaryPoints(segment, oldsegment):
    a = segment['points'][len(segment['points'])-1]
    b = oldsegment['points'][len(oldsegment['points'])-1]
    deltilex = segment['x']-oldsegment['x']
    deltiley = segment['y']-oldsegment['y']
    delx = a[0]-(b[0] - 255*deltilex)
    dely = a[1]-(b[1] - 255*deltiley)
    if delx==0:
        mida = [a[0], round(float(a[1])/255.0)*255]
        midb = [b[0], round(float(b[1])/255.0)*255]
        oldsegment['points'].append(midb)
        segment['points'].insert(0, mida)
    else:    
        m = float(dely)/float(delx)
        if deltilex!=0:
            midax = round(float(a[0])/255.0)*255
            miday = math.ceil(a[1] - m*(a[0]-midax))
            midbx = round(float(b[0])/255.0)*255
            midby = math.ceil(b[1] + m*(midbx - b[0]))
            oldsegment['points'].append([midbx, midby])
            segment['points'].insert(0, [midax, miday])
        else:
            miday = round(float(a[1])/255.0)*255
            midax = math.ceil(a[0] - (a[1]-miday)/m)
            midby = round(float(b[1])/255.0)*255
            midbx = math.ceil(b[0] + (midby - b[1])/m)
            oldsegment['points'].append([midbx, midby])
            segment['points'].insert(0, [midax, miday])

# each track segment needs a tile x,y, then a list of points that go from the boundary of the tile to the end point/another tile boundary, need separate storage element for each track segment (need new elem everytime a boundary is crossed)
def parseGPX(gpxfile, zoom):
    ns = {'url': 'http://www.topografix.com/GPX/1/1'} #namespace for gpx file format
    tree = eltree.parse(gpxfile)
    root = tree.getroot()
    oldtilex = -1
    oldtiley = -1
    segments = []
    segment = {'x':oldtilex, 'y':oldtiley, 'points':[]}
    points = []
    oldsegment = {}
    for trkpt in root.findall("./url:trk/url:trkseg/url:trkpt", ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))
        pxpt = coord2px(lat, lon, zoom) #convert lat and lon to web mercator pixels at given zoom level
        tilex = int(math.floor(pxpt[0]/256))
        tiley = int(math.floor(pxpt[1]/256))
        pxpt[0] = pxpt[0]%256
        pxpt[1] = pxpt[1]%256
        
        points.append(pxpt)
        if (tilex != oldtilex or tiley != oldtiley): #check if tile boundary was crossed
            #print("changed tiles")
            oldsegment = segment
            segment = {'x':tilex, 'y':tiley, 'points':[]}
            if oldtilex != -1:
                segment = {'x':tilex, 'y':tiley, 'points':[]}
                segment['points'].append(pxpt)
                addBoundaryPoints(segment, oldsegment) #adding new points that connect each segment to the edge of their tile
                segments.append(oldsegment)
        else:
            segment['points'].append(pxpt)
        oldtilex = tilex
        oldtiley = tiley
    segments.append(segment)
    return segments

def plotPoints(points):
    zippoints = list(zip(*points))
    plt.scatter(zippoints[0], zippoints[1], s=None, c=None, marker='.')
    plt.xlim(0, 256)
    plt.ylim(256, 0)
    plt.show()
    #print(zippoints)

def main():
    zoom = 17
    segments = parseGPX("/Users/jtblair/Downloads/activity_4400110058.gpx", zoom)
    # TODO: loop through segments, output tiles using line algorithm
    plotPoints(segments[3]['points'])
    plotPoints(segments[4]['points'])
    plotPoints(segments[5]['points'])


if __name__ == "__main__":
    main()
