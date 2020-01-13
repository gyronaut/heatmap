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

# TODO fix bug with boundary points... (adding points to corners?)
def addBoundaryPoints(segment, tilenum, oldsegment, oldtilenum):
    a = segment[0]
    b = oldsegment[len(oldsegment)-1]
    deltilex = (tilenum%(2<<16)) - (oldtilenum%(2<<16))
    deltiley = (tilenum >> 17) - (oldtilenum >> 17)
    delx = a[0]-(b[0] - 255*deltilex)
    dely = a[1]-(b[1] - 255*deltiley)
    print(a,b)
    print(delx, dely)
    mida = []
    midb = []
    if delx==0:
        mida = [a[0], round(float(a[1])/255.0)*255]
        midb = [b[0], round(float(b[1])/255.0)*255]
        oldsegment.append(midb)
        segment.insert(0, mida)
    elif dely==0:
        mida = [round(float(a[0])/255.0)*255, a[1]]
        midb = [round(float(b[0])/255.0)*255, b[1]]
        oldsegment.append(midb)
        segment.insert(0, mida)
    else:    
        m = float(dely)/float(delx)
        if deltilex!=0:
            midax = round(float(a[0])/255.0)*255
            miday = math.ceil(a[1] - m*(a[0]-midax))
            midbx = round(float(b[0])/255.0)*255
            midby = math.ceil(b[1] + m*(midbx - b[0]))
            mida = [midax, miday]
            midb = [midbx, midby]
            oldsegment.append([midbx, midby])
            segment.insert(0, [midax, miday])
        else:
            miday = round(float(a[1])/255.0)*255
            midax = math.ceil(a[0] - (a[1]-miday)/m)
            midby = round(float(b[1])/255.0)*255
            midbx = math.ceil(b[0] + (midby - b[1])/m)
            mida = [midax, miday]
            midb = [midbx, midby]
            oldsegment.append([midbx, midby])
            segment.insert(0, [midax, miday])
    print(mida, midb)

# each track segment needs a tile x,y, then a list of points that go from the boundary of the tile to the end point/another tile boundary, need separate storage element for each track segment (need new elem everytime a boundary is crossed)
def parseGPX(gpxfile, zoom):
    ns = {'url': 'http://www.topografix.com/GPX/1/1'} #namespace for gpx file format
    tree = eltree.parse(gpxfile)
    root = tree.getroot()
    oldtilex = 0
    oldtiley = 0
    oldtilenum = 0;
    segments = []
    tiles = {}
    points = []
    oldsegment = {}
    for trkpt in root.findall("./url:trk/url:trkseg/url:trkpt", ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))
        pxpt = coord2px(lat, lon, zoom) #convert lat and lon to web mercator pixels at given zoom level
        tilex = int(math.floor(pxpt[0]/256))
        tiley = int(math.floor(pxpt[1]/256))
        tilenum = (tiley << 17) + tilex
        #print("tilex: " + str(tilex) + ", " + str(tilenum%(2<<16)))
        #print("tiley: " + str(tiley) + ", " + str(tilenum >> 17))
        pxpt[0] = pxpt[0]%256
        pxpt[1] = pxpt[1]%256
        
        if (tilenum != oldtilenum): #check if tile boundary was crossed
            #print("changed tiles")
            oldpoints = points.copy()
            points = [pxpt]
            if oldtilenum != 0:
                addBoundaryPoints(points, tilenum, oldpoints, oldtilenum) #adding new points that connect each segment to the edge of their tile
                if str(oldtilenum) in list(tiles):
                    print("adding new segment to existing tile entry")
                    tiles[str(oldtilenum)].append(oldpoints)
                else:
                    tiles[str(oldtilenum)] = [[]]
                    tiles[str(oldtilenum)].append(oldpoints)
        else:
             points.append(pxpt) 

        oldtilex = tilex
        oldtiley = tiley
        oldtilenum = tilenum

    if str(oldtilenum) in list(tiles):
        tiles[str(oldtilenum)].append(points)
    else:
        tiles[str(oldtilenum)] = [[]]
        tiles[str(oldtilenum)].append(points)

    return tiles

def plotPoints(points):
    #print(points)
    xpts = []
    ypts = []
    for i in range(1, len(points)):
        for pt in points[i]:
            xpts.append(pt[0])
            ypts.append(pt[1])

    #zippoints = list(zip(*points[1]))
    #zippoints = [list(zippoints[0]), list(zippoints[1])]
    #for i in range(2, len(points)):
    #        zp = list(zip(*points[i]))
    #        print(zp)
    #        zippoints[0].append(list(zp[0]))
    #        zippoints[1].append(list(zp[1]))
    #plt.scatter(zippoints[0], zippoints[1], s=None, c=None, marker='.')
    plt.scatter(xpts, ypts, s=None, c=None, marker='.')
    plt.xlim(0, 256)
    plt.ylim(256, 0)
    plt.show()
    #print(zippoints)

def main():
    zoom = 15
    tiles = parseGPX("/Users/jtblair/Downloads/activity_4400110058.gpx", zoom)
    print(list(tiles))
    # TODO: loop through segments, output tiles using line algorithm
    #plotPoints(tiles[list(tiles)[3]])
    #plotPoints(segments[4]['points'])
    #plotPoints(segments[5]['points'])
    for tile in list(tiles):
        plotPoints(tiles[tile])


if __name__ == "__main__":
    main()
