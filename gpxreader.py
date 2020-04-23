import math
import random
import xml.etree.ElementTree as eltree
import matplotlib.pyplot as plt
import png
import os
import fnmatch

# TODO: figure out how to log-in and authenticate before retreiving activity data

# url for json string of every activity in 2020: 
# https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?activityType=running&startDate=2020-01-01

# url for downloading specific garmin gpx track:
# https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/' + activityId
# as seen here: https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-web/63103/show-all-routes-on-the-same-map/930931#930931

# tiles covering relavant portion of Austin (Zoom 11): Google - (467, 842), (468, 842), (467, 843), (468, 843)  ;  TSM - (467, 1205), (468, 1205), (467, 1204), (468, 1204)

class RunData():
    def __init__(self, zoom):
        self.zoom = zoom;
        self.datachunks = {}

    def coord2px(self, lat, lon):
        x = 256.0/(2.0*math.pi)*(2**self.zoom)*((lon)*math.pi/180.0 + math.pi)
        y = 256.0/(2.0*math.pi)*(2**self.zoom)*(math.pi - math.log(math.tan(math.pi/4.0 + (lat*math.pi/180.0)/2.0)))
        return [int(x),int(y)]
    
    def _addBoundaryPoints(self, segment, tilenum, oldsegment, oldtilenum):
        a = segment[0]
        b = oldsegment[len(oldsegment)-1]
        deltilex = (tilenum%(2<<16)) - (oldtilenum%(2<<16))
        deltiley = (tilenum >> 17) - (oldtilenum >> 17)
        delx = a[0]-(b[0] - 256*deltilex)
        dely = a[1]-(b[1] - 256*deltiley)
        mida = [0,0]
        midb = [0,0]
        if delx==0:
            mida = [a[0], round(float(a[1])/255.0)*255]
            midb = [b[0], round(float(b[1])/255.0)*255]
        elif dely==0:
            mida = [round(float(a[0])/255.0)*255, a[1]]
            midb = [round(float(b[0])/255.0)*255, b[1]]
        else:    
            m = float(dely)/float(delx)
            if deltiley==0:
                midax = round(float(a[0])/255.0)*255
                miday = round(a[1] - m*(a[0]-(midax - (deltilex*0.499))))
                midbx = round(float(b[0])/255.0)*255
                midby = round(b[1] + m*((midbx + (deltilex*0.499)) - b[0]))
                mida = [midax, miday]
                midb = [midbx, midby]
            elif deltilex==0:
                miday = round(float(a[1])/255.0)*255
                midax = round(a[0] - (a[1]-(miday - deltiley*0.499))/m)
                midby = round(float(b[1])/255.0)*255
                midbx = round(b[0] + ((midby + deltiley*0.499) - b[1])/m)
                mida = [midax, miday]
                midb = [midbx, midby]
            else:
                if((a[0]-(round(float(a[0])/255.0)*255.0))*dely > (a[1]-round(float(a[1])/255.0)*255)*delx):
                    intertilex = tilenum%(2<<16)
                    intertiley = (tilenum >> 17) - deltiley
                    intertilenum = (intertiley << 17) + intertilex
                    mida[1] = round(float(a[1])/255.0)*255
                    mida[0] = round(a[0] - (a[1]-mida[1])/m)
                    midb[0] = round(float(b[0])/255.0)*255
                    midb[1] = round(b[1] + m*(midb[0] - b[0]))

                    midc = [math.ceil(mida[0] - 1.0/m), abs(mida[1]-255)]
                    midd = [abs(midb[0]-255), math.floor(midb[1]+m)]
                    intersegment = [midc, midd]
                    #print(intersegment, intertilex, intertiley, "test")
                    if intertilenum in self.datachunks:
                        self.datachunks[intertilenum].append(intersegment)
                    else:
                        self.datachunks[intertilenum] = [[]]
                        self.datachunks[intertilenum].append(intersegment)
            
                elif((a[0]-(round(float(a[0])/255.0)*255.0)*dely) < (a[1]-round(float(a[1])/255.0)*255)*delx):
                    intertilex = tilenum%(2<<16) - deltiley
                    intertiley = (tilenum >> 17)
                    intertilenum = (intertiley << 17) + intertilex
                    mida[0] = round(float(a[0])/255.0)*255
                    mida[1] = round(a[1] - m*(a[0]-mida[0]))
                    midb[1] = round(float(b[1])/255.0)*255
                    midb[0] = round(b[0] + (midb[1] - b[1])/m)

                    midc = [abs(mida[0] - 255), math.floor(mida[1] - m)]
                    midd = [math.floor(midb[0]+1.0/m), abs(midb[1]-255)]
                    intersegment = [midc, midd]
                    #print(intersegment, intertilex, intertiley, intertilenum)
                    if intertilenum in self.datachunks:
                        self.datachunks[intertilenum].append(intersegment)
                    else:
                        self.datachunks[intertilenum] = [[]]
                        self.datachunks[intertilenum].append(intersegment)

                else:
                    mida = [round(float(a[0])/255.0)*255, round(float(a[1])/255.0)*255]
                    midb = [round(float(b[0])/255.0)*255, round(float(b[1])/255.0)*255]

        if(b[0] != midb[0] or b[1] != midb[1]):
            oldsegment.append(midb)
        if(a[0] != mida[0] or a[1] != mida[1]):
            segment.insert(0, mida)

    def readInGPX(self, gpxfile):
        ns = {'url': 'http://www.topografix.com/GPX/1/1'} #namespace for gpx file format
        tree = eltree.parse(gpxfile)
        root = tree.getroot()
        oldtilex = 0
        oldtiley = 0
        oldtilenum = 0;
        segments = []
        points = []
        oldsegment = {}
        oldpxpt = [-1, -1]
        for trkpt in root.findall("./url:trk/url:trkseg/url:trkpt", ns):
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
            pxpt = self.coord2px(lat, lon) #convert lat and lon to web mercator pixels at given zoom level
            tilex = int(math.floor(pxpt[0]/256))
            tiley = int(math.floor(pxpt[1]/256))
            tilenum = (tiley << (self.zoom+1)) + tilex
            pxpt[0] = pxpt[0]%256
            pxpt[1] = pxpt[1]%256
        
            if (oldpxpt[0]==pxpt[0] and oldpxpt[1]==pxpt[1]): #check that next point isn't identical to last point
                continue
            if (tilenum != oldtilenum): #check if tile boundary was crossed
                oldpoints = points.copy()
                points = [pxpt]
                if oldtilenum != 0:
                    self._addBoundaryPoints(points, tilenum, oldpoints, oldtilenum) #adding new points that connect each segment to the edge of their tile
                    if oldtilenum in self.datachunks:
                        self.datachunks[oldtilenum].append(oldpoints)
                    else:
                        self.datachunks[oldtilenum] = [[]]
                        self.datachunks[oldtilenum].append(oldpoints)
            else:
                 points.append(pxpt) 
    
            oldtilex = tilex
            oldtiley = tiley
            oldtilenum = tilenum
            oldpxpt = pxpt

        if oldtilenum in self.datachunks:
            self.datachunks[oldtilenum].append(points)
        else:
            self.datachunks[oldtilenum] = [[]]
            self.datachunks[oldtilenum].append(points)



class TileSet():

    def __init__(self, zoom):
        self.zoom = zoom
        self.tiles = {}
        self.PDF = [0]*1000
        self.CDF = [0]*1000
        self.deciles = []
        self.tilebounds = []

    def copy(self):
        dup = TileSet(self.zoom)
        dup.tiles = self.tiles.copy()
        dup.PDF = self.PDF.copy()
        dup.CDF = self.CDF.copy()
        dup.deciles = self.deciles.copy()
        dup.tilebounds = self.tilebounds.copy()
        return dup


    def initFromRunData(self, data):
        for tilenum in data.datachunks:
             self.pts2matrix(tilenum, data.datachunks[tilenum])
        self._calcPDF()
        self._calcCDF()
        self._calcDecileCutoffs()
        self.getTileBounds()

    def pts2matrix(self, tilenum, tiledata):
        mat = [0]*256*256
        for segment in tiledata:
            length  = len(segment)
            if length == 0:
                continue
            for ipt in range(0, length-1):
                try:
                    self.plot(segment[ipt][0], segment[ipt][1], mat)
                except:
                    print("broke at line segment:", segment, tile, tiledata)
                self.plotLine(segment[ipt][0], segment[ipt][1], segment[ipt+1][0], segment[ipt+1][1], mat)
            self.plot(segment[length-1][0], segment[length-1][1], mat)
        self.tiles[tilenum] = mat
    
    def plotLine(self, x0, y0, x1, y1, mat):
        dx = abs(x1-x0)
        dy = abs(y1-y0)
        sx = (1 if x1>x0 else -1)
        sy = (1 if y1>y0 else -1)
        if(dy < dx):
            if(sx > 0):
                self.plotLineLow(x0, y0, x1, y1, mat)
            else:
                self.plotLineLow(x1, y1, x0, y0, mat)
        else:
            if(sy > 0):
                self.plotLineHigh(x0, y0, x1, y1, mat)
            else:
                self.plotLineHigh(x1, y1, x0, y0, mat)

    def plot(self, x, y, mat):
        mat[x+(256*y)]+=1

    def plotLineLow(self, x0, y0, x1, y1, mat):
        dx = x1-x0
        dy = y1-y0
        ystep = 1
        if(dy < 0):
            ystep = -1
            dy = -dy
        D = (dy<<1) -dx
        y = y0
        if(D > 0):
            y = y + ystep
            D = D-(dx<<1)
        D = D + (dy<<1)
        for x in range(x0+1, x1):
            self.plot(x, y, mat)
            if(D > 0):
                y = y + ystep
                D = D-(dx<<1)
            D = D + (dy<<1)


    def plotLineHigh(self, x0, y0, x1, y1, mat):
        dx = x1-x0
        dy = y1-y0
        xstep = 1
        if(dx < 0):
            xstep = -1
            dx = -dx
        D = (dx<<1) - dy
        x = x0
        if(D > 0):
            x = x + xstep
            D = D-(dy<<1)
        D = D + (dx<<1)
        for y in range(y0+1, y1):
            self.plot(x, y, mat)
            if(D > 0):
                x = x + xstep
                D = D-(dy<<1)
            D = D + (dx<<1)

    def _calcPDF(self):
        numMat = 10
        if(numMat > len(self.tiles)):
            numMat = len(self.tiles)
        data = []
        imat = 0
        for tile in self.tiles:
            if (imat >= numMat):
                break
            data = data + self.tiles[tile]
            imat+=1
        data.sort(reverse = True)
        self.PDF = [0]*1000
        sample = random.sample(range(0, 256*256), 20000)
        for idx in sample:
            pt = data[idx]
            if(pt>999):
                pt=999
            self.PDF[pt]+=1


    def _calcCDF(self):
        tot = 0
        for i in range(0,len(self.PDF)):
            self.CDF[i] = (self.PDF[i]+tot)/20000.0
            tot+=self.PDF[i]

    def _calcDecileCutoffs(self):
        cdfSteps = [0]*20
        istep = 1
        offset = self.CDF[0]
        step = (1.0-offset)/10.0
        for i in range(1,len(self.CDF)):
            if(self.CDF[i]>=(offset+(istep*step))):
                cdfSteps[istep] = i
                if(self.CDF[i]> offset+(step*(istep+1))):
                    skipsteps = int((self.CDF[i]-offset)/step)-istep
                    for j in range(1, skipsteps+1):
                        cdfSteps[istep+j] = i
                    istep+= skipsteps
                else:
                    istep+=1
        self.deciles = [0]*(istep)
        for i in range(0, istep):
            self.deciles[i] = cdfSteps[i]
        self.deciles.append(999)

    def normalize(self):
        for tile in self.tiles:
            for ipx in range(0, len(self.tiles[tile])):
                px = self.tiles[tile][ipx]
                for i in range(0, len(self.deciles)-1):             
                    if (px > self.deciles[i] and px <= self.deciles[i+1]):
                        self.tiles[tile][ipx] = i+1
                        break

    def saveTileAsPNG(self, mapfolder, tilenum, p, bd):
        x = tilenum%(2<<(self.zoom))
        y = tilenum>>(self.zoom+1)
        if not os.path.exists(mapfolder+str(self.zoom)+"/"+str(x)):
            os.mkdir(mapfolder+str(self.zoom)+"/"+str(x))

        w = png.Writer(size=(256,256), palette = p, bitdepth = bd)            
        rows = w.array_scanlines(self.tiles[tilenum])
        f = open(mapfolder+str(self.zoom)+"/"+str(x)+"/"+str(y)+".png", "wb")
        w.write(f, rows)
        f.close()
    
    def makeGradientPalette(self, bg, low, high, bd):
        palette = [bg]
        rstep = int((high[0]-low[0])/(len(self.deciles)-2))
        gstep = int((high[1]-low[1])/(len(self.deciles)-2))
        bstep = int((high[2]-low[2])/(len(self.deciles)-2))
        dupcount = 1
        for i in range(0, len(self.deciles)-2):
            if(self.deciles[i+1] == self.deciles[i+2]): #check if 1 value covers more than one decile bin 
                dupcount+=1
            else:
                if(dupcount >1):    #in case 1 value in cdf covers more than one decile bin i.e. there is a duplicated number in cdf
                    n = i-dupcount+1
                    dupstep = (i*(i+1) - n*(n+1))/(2.0*dupcount) #calc average i value over the duplicated bins ('Sum of ints from k to n' = n(n+1)/2 - k(k+1)/2)
                    for dup in range(i-dupcount, i):
                        palette.append((int(low[0]+dupstep*rstep), int(low[1]+dupstep*gstep), int(low[2]+dupstep*bstep), low[3]))
                else:
                    palette.append((int(low[0]+i*rstep), int(low[1]+i*gstep), int(low[2]+i*bstep), low[3]))
                dupcount = 1
        for j in range(len(palette), 1<<bd):
            palette.append(high)
        return palette

    def savePaletteAsPNG(self, palette, name):
        mat = [0]*100*40;
        for x in range(25,75):
            i = math.floor((x-25.)/5.)
            for y in range(10,30):
                mat[x*100 + y] = palette[i]        
        w = png.Writer(size=(100,40), palette = palette, bitdepth = 8);


    def getTileBounds(self):
        xmin = 2<<self.zoom
        xmax = -1
        ymin = 2<<self.zoom
        ymax = -1
        for tile in self.tiles:
            if(tile%(2<<self.zoom) > xmax):
                xmax = tile%(2<<self.zoom)
            if(tile%(2<<self.zoom) < xmin):
                xmin = tile%(2<<self.zoom)
            if(tile>>(self.zoom+1) > ymax):
                ymax = tile>>(self.zoom+1)
            if(tile>>(self.zoom+1) < ymin):
                ymin = tile>>(self.zoom+1)
        self.tilebounds = [xmin, ymin, xmax, ymax]


    def zoomOutTile(self, tilex, tiley, has_data):
        zoom = self.zoom-1
        zmatrix = [0]*256*256
        for i in range(0, 4):
            if(has_data[i]):
                mat = self.tiles[((tiley+(i>>1))<<(zoom+2))+(tilex+(i%2))]
                for row in range(0, 128):
                    for col in range(0, 128):
                        zrow = 128*(i>>1)+row
                        zcol = 128*(i%2)+col
                        zmatrix[(zrow<<8)+zcol] = mat[(row<<9)+(col<<1)]+mat[(row<<9)+(col<<1)+1]+mat[(row<<9) + 256 + (col<<1)]+mat[(row<<9)+256+(col<<1)+1]
        return zmatrix

    def makeZoomedOutTileset(self):
        print(self.tilebounds)
        zoom = self.zoom -1
        zoomTiles = TileSet(zoom)
        #starting at min y row, find all tiles 1 above or below and create tiles just for those that have at least 1 sub-tile filled
        yrow = self.tilebounds[1]
        while(yrow < self.tilebounds[3]+2):
            xcol = self.tilebounds[0]
            while(xcol < self.tilebounds[2]+2):
                has_data = [False, False, False, False]
                y0 = yrow-(yrow%2)
                y1 = y0+1
                has_data[0+(xcol%2)] = ((y0<<zoom+2)+xcol in self.tiles)
                has_data[2+(xcol%2)] = ((y1<<zoom+2)+xcol in self.tiles)
                if(True in has_data):
                    #check 1 col right for tiles with data (only if x even)
                    if(xcol%2==0):
                        has_data[1] = ((y0<<zoom+2)+xcol+1 in self.tiles)
                        has_data[3] = ((y1<<zoom+2)+xcol+1 in self.tiles)
                    x0 = xcol -(xcol%2)
                    zoomTiles.tiles[(y0<<(zoomTiles.zoom))+(x0>>1)] = self.zoomOutTile(x0, y0, has_data)
                    xcol+=2-(xcol%2)
                else:
                    xcol+=1
            yrow += 2

        zoomTiles._calcPDF()
        zoomTiles._calcCDF()
        zoomTiles._calcDecileCutoffs()
        zoomTiles.getTileBounds()
        return zoomTiles



def main():
    zoommax = 16
    zoommin = 12
    tiles = {}
    files = []
    filelocation = "/Users/jtblair/Downloads/"
    mapfolder = "map/"
    data = RunData(zoommax)

    for f in os.listdir(filelocation):
        if fnmatch.fnmatch(f, "activity_4*.gpx"):
            files.append(f)

    for f in files:
        data.readInGPX(filelocation+f)
    
    
    #data.readInGPX("/Users/jtblair/Downloads/activity_4662086957.gpx") #test activity showing missing boundary segments (FIXED)
    zoom = zoommax
    if not os.path.exists(mapfolder+str(zoom)):
            os.mkdir(mapfolder+str(zoom))

    matrices = TileSet(zoom)
    matrices.initFromRunData(data)
    #for tile in matrices.tiles:
        #print(tile>>zoom)
    #palette = matrices.makeGradientPalette((30,30,30,200), (60,30,155,200), (130,240,255,200), 8); #blue-purple
    palette = matrices.makeGradientPalette((15,15,15,200), (60,40,150,225), (255,195,210,225), 8); #pink-purple
    print(matrices.deciles)
    print(palette[:10])
    for zlevel in range(1, zoommax - zoommin +1):
        zoom = zoommax - zlevel
        print(zoom)
        if not os.path.exists(mapfolder+str(zoom)):
            os.mkdir(mapfolder+str(zoom))
        zoommatrices = matrices.makeZoomedOutTileset()
        matrices.normalize()
        for matrix in matrices.tiles:
            matrices.saveTileAsPNG(mapfolder, matrix, palette, 8) 

        matrices = zoommatrices.copy()
        #palette = matrices.makeGradientPalette((30,30,30,150), (60,30,155,200), (130,240,255,200), 8);
        palette = matrices.makeGradientPalette((15,15,15,200), (60,40,150,225), (255,195,210,225), 8); #pink-purple
        print(matrices.deciles)
        print(palette[:10]);
    matrices.normalize()    
    for matrix in matrices.tiles:
        matrices.saveTileAsPNG(mapfolder, matrix, palette, 8); 

if __name__ == "__main__":
    main()
