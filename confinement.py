#imports
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, MultiLineString

class Confinement:
    """
    Calculates confinement for each reach of an input drainage network and adds an attribute with this value
    """
    def __init__(self, network, valley, exag=0.5):
        """
        :param network: string - path to drainage network shapefile.
        :param valley: string - path to valley bottom shapefile.
        :param exag: float - a proportion (0 - 1) of the stream network width at each segment to add to the buffer
        width to ensure overlap with the valley bottom polygon. Default = 0.5.
        """
        self.streams = network
        self.network = gpd.read_file(network)
        self.valley = gpd.read_file(valley)
        self.exag = exag
        
        # check for projection

        # set confinement value to default nodata
        self.network['confine'] = -9999.99
        
        # set up container for confining margin line features;
        self.margins = []

    def calc_confinement(self, seg, buf_width):
        
        channel = seg.buffer(buf_width)
        buf = seg.buffer(3*buf_width)  # instead of fixed with do 3*bufwidth?
        inters1 = self.valley['geometry'].intersection(buf) 
        
  
        # get intersection with only valley bottom feature that intersects network segment
        print('finding vb section')
        sections = []
        for i in range(len(inters1)):
            if inters1[i].is_empty == False:
                sections.append(i)
        #print('sections :', sections)
        # may intersect with more than one valley feature. Narrow down to the largest one
        if len(sections) > 1:
            section = None
            area = 0
            for i in sections:
                if self.valley.loc[i, 'geometry'].area > area:
                    area = self.valley.loc[i, 'geometry'].area
                    section = i
        elif len(sections) == 1:
            section = sections[0]
        
        if 'section' in locals():
            print('vb section: ', section)
            vb_sec = self.valley.loc[section, 'geometry']
        else:
            return 1
        
        inters2 = vb_sec.intersection(buf)
        
        dif = channel.difference(inters2)
        inters = channel.intersection(inters2)
        
        # In the case there's no difference because it's fully unconfined
        print('determining if no difference')
        if dif.type == 'Polygon':
            if len(dif.exterior.xy[0]) == 0:
                return 0
                
        print('checking intersection area')
        if inters.area == 0:
                return 1
        
        print('getting intersection coordinates')
        if inters.type == 'MultiPolygon':
            int_coords = []
            for i in range(len(inters)):
                for j in range(len(inters[i].exterior.xy[0])):
                    int_coords_x = inters[i].exterior.xy[0][j]
                    int_coords_y = inters[i].exterior.xy[1][j]
                    int_coords.append([int_coords_x, int_coords_y])
        elif inters.type == 'Polygon':
            int_coords = []
            for i in range(len(inters.exterior.xy[0])):
                int_coords_x = inters.exterior.xy[0][i]
                int_coords_y = inters.exterior.xy[1][i]
                int_coords.append([int_coords_x, int_coords_y])
        else:
            int_coords = []
                
        print('comparing difference coordinates to intersection coordinates')
        if dif.type == 'MultiPolygon':
            line_len = []
            lines = []
            for i in range(len(dif)):
                line_coords = []
                for j in range(len(dif[i].exterior.xy[0])):
                    dif_coords_x = dif[i].exterior.xy[0][j]
                    dif_coords_y = dif[i].exterior.xy[1][j]
                    if [dif_coords_x, dif_coords_y] in int_coords:
                        if [dif_coords_x, dif_coords_y] not in line_coords:
                            line_coords.append([dif_coords_x, dif_coords_y])
                if len(line_coords) > 1:
                    line = LineString(line_coords)
                    lines.append(line)
                    # self.margins.append(line)
                    line_len.append(line.length)
            self.margins.append(MultiLineString(lines))

        elif dif.type == 'Polygon':
            line_len = []
            line_coords = []
            for y in range(len(dif.exterior.xy[0])):
                dif_coords_x = dif.exterior.xy[0][y]
                dif_coords_y = dif.exterior.xy[1][y]
                if [dif_coords_x, dif_coords_y] in int_coords:
                    line_coords.append([dif_coords_x, dif_coords_y])
            if len(line_coords) > 1:
                line = LineString(line_coords)
                self.margins.append(line)
                line_len.append(line.length)
            else:
                line_len = []
        else:
            line_len = []

        if len(int_coords) == 0:
            return 1.  # stream network and valley bottom misaligned
        elif len(line_len) == 0:
            return 0.  # no overlap, stream is fully unconfined
        else:
            return min(1., np.sum(line_len) / (2*seg.length))

    def confinement(self):

        for i in self.network.index:
            print('segment ', i+1, ' of ', len(self.network.index))
            seg = self.network.loc[i, 'geometry']
            buf_width = max(10., (self.network.loc[i, 'BFwidth']/2) + (self.network.loc[i, 'BFwidth']*self.exag))

            conf_val = self.calc_confinement(seg, buf_width)

            self.network.loc[i, 'confine'] = conf_val

        self.network.to_file(self.streams)

        return
    
    def save_margins(self, margin_out_path):
        
        if len(self.margins)>0:
            cm_df = gpd.GeoSeries(self.margins)
            cm_df.crs = self.network.crs
        
            cm_df.to_file(margin_out_path)
        else:
            pass