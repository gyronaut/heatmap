import math
import xml.etree.ElementTree as eltree
import matplotlib.pyplot as plt
import png

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

def addBoundaryPoints(segment, tilenum, oldsegment, oldtilenum):
    a = segment[0]
    b = oldsegment[len(oldsegment)-1]
    deltilex = (tilenum%(2<<16)) - (oldtilenum%(2<<16))
    deltiley = (tilenum >> 17) - (oldtilenum >> 17)
    delx = a[0]-(b[0] - 256*deltilex)
    dely = a[1]-(b[1] - 256*deltiley)
    mida = []
    midb = []
    if delx==0:
        mida = [a[0], round(float(a[1])/255.0)*255]
        midb = [b[0], round(float(b[1])/255.0)*255]
    elif dely==0:
        mida = [round(float(a[0])/255.0)*255, a[1]]
        midb = [round(float(b[0])/255.0)*255, b[1]]
    else:    
        m = float(dely)/float(delx)
        if deltilex!=0:
            midax = round(float(a[0])/255.0)*255
            miday = math.ceil(a[1] - m*(a[0]-midax))
            midbx = round(float(b[0])/255.0)*255
            midby = math.ceil(b[1] + m*(midbx - b[0]))
            mida = [midax, miday]
            midb = [midbx, midby]
        else:
            miday = round(float(a[1])/255.0)*255
            midax = math.ceil(a[0] - (a[1]-miday)/m)
            midby = round(float(b[1])/255.0)*255
            midbx = math.ceil(b[0] + (midby - b[1])/m)
            mida = [midax, miday]
            midb = [midbx, midby]
    oldsegment.append(midb)
    segment.insert(0, mida)

# each track segment needs a tile x,y, then a list of points that go from the boundary of the tile to the end point/another tile boundary, need separate storage element for each track segment (need new elem everytime a boundary is crossed)
def parseGPX(gpxfile, zoom, tiles):
    ns = {'url': 'http://www.topografix.com/GPX/1/1'} #namespace for gpx file format
    tree = eltree.parse(gpxfile)
    root = tree.getroot()
    oldtilex = 0
    oldtiley = 0
    oldtilenum = 0;
    segments = []
    points = []
    oldsegment = {}
    for trkpt in root.findall("./url:trk/url:trkseg/url:trkpt", ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))
        pxpt = coord2px(lat, lon, zoom) #convert lat and lon to web mercator pixels at given zoom level
        tilex = int(math.floor(pxpt[0]/256))
        tiley = int(math.floor(pxpt[1]/256))
        tilenum = (tiley << 17) + tilex
        pxpt[0] = pxpt[0]%256
        pxpt[1] = pxpt[1]%256
        
        if (tilenum != oldtilenum): #check if tile boundary was crossed
            oldpoints = points.copy()
            points = [pxpt]
            if oldtilenum != 0:
                addBoundaryPoints(points, tilenum, oldpoints, oldtilenum) #adding new points that connect each segment to the edge of their tile
                if str(oldtilenum) in list(tiles):
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

def plot(x, y, mat):
   # if(x+y*256 >= len(mat)):
   #     print(x,y, len(mat))
   # print(x, y, (x+(256*y)))
    mat[x+(256*y)]+=1

def plotLineLow(x0, y0, x1, y1, mat):
    dx = x1-x0
    dy = y1-y0
    ystep = 1
    if(dy < 0):
        ystep = -1
        dy = -dy
    D = (dy<<1) -dx
    y = y0
    for x in range(x0, x1+1):
        plot(x, y, mat)
        if(D > 0):
            y = y + ystep
            D = D-(dx<<1)
        D = D + (dy<<1)

def plotLineHigh(x0, y0, x1, y1, mat):
    dx = x1-x0
    dy = y1-y0
    xstep = 1
    if(dx < 0):
        xstep = -1
        dx = -dx
    D = (dx<<1) - dy
    x = x0
    for y in range(y0, y1+1):
        plot(x, y, mat)
        if(D > 0):
            x = x + xstep
            D = D-(dy<<1)
        D = D + (dx<<1)

# TODO: figure out how to prevent double counting at start and end points of lines
def plotLine(x0, y0, x1, y1, mat):
    dx = abs(x1-x0)
    dy = abs(y1-y0)
    sx = (1 if x1>x0 else -1)
    sy = (1 if y1>y0 else -1)
    if(dy < dx):
        if(sx > 0):
            plotLineLow(x0, y0, x1, y1, mat)
        else:
            plotLineLow(x1, y1, x0, y0, mat)
    else:
        if(sy > 0):
            plotLineHigh(x0, y0, x1, y1, mat)
        else:
            plotLineHigh(x1, y1, x0, y0, mat)

def tile2matrix(segments):
    mat = [0]*256*256
    print(len(mat))
    for segment in segments:
        if len(segment) == 0:
            continue
        for ipt in range(0, len(segment)-1):
            plotLine(segment[ipt][0], segment[ipt][1], segment[ipt+1][0], segment[ipt+1][1], mat)
    return mat


def pyplotPoints(points):
    xpts = []
    ypts = []
    for i in range(1, len(points)):
        for pt in points[i]:
            xpts.append(pt[0])
            ypts.append(pt[1])
    plt.scatter(xpts, ypts, s=None, c=None, marker='.')
    plt.xlim(0, 256)
    plt.ylim(256, 0)
    plt.show()

def main():
    zoom = 16
    tiles = {}
    parseGPX("/Users/jtblair/Downloads/activity_4400110058.gpx", zoom, tiles)
    parseGPX("/Users/jtblair/Downloads/activity_4425559408.gpx", zoom, tiles)
    print(list(tiles))
    # TODO: loop through tiles to output data in arrays   
    #pyplotPoints(tiles[tile])
    pyplotPoints(tiles[list(tiles)[4]])
    mat = tile2matrix(tiles[list(tiles)[4]]) #connect points using bresenham's line algorithm, output tiles as 256x256 arrays
    testpoints = [[], [[10, 10], [11,11], [11, 20], [12,21], [11,22], [22,22], [25,27], [25, 35], [24, 36]]]
    testmat = tile2matrix(testpoints)
    w = png.Writer(size=(256,256), greyscale=True, bitdepth = 2)
    rows = w.array_scanlines(testmat)
    f = open("test.png", "wb")
    w.write(f, rows)
    f.close()


if __name__ == "__main__":
    main()
