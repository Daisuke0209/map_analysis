import numpy as np
from math import pi
from math import e
from math import atan
import urllib.request
import cv2
from pygeocoder import Geocoder
import googlemaps
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import ArrowStyle
from PIL import Image
import os

def sec(x):
    return 1/np.cos(x)

def pole2tile(lat, lon, zoom):
    n = 2**zoom
    tile_lon = (n * (lon + 180))/360
    lat_rad = lat * pi / 180
    tile_lat = (n * (1 - np.log(np.tan(lat_rad) + sec(lat_rad)) / pi)) / 2
    return tile_lat,tile_lon

def tile2pole(tile_lat, tile_lon, zoom):
	lon = (tile_lon / 2.0**zoom) * 360 - 180 # 経度（東経）
	mapy = (tile_lat / 2.0**zoom) * 2 * pi - pi
	lat = 2 * atan(e ** (- mapy)) * 180 / pi - 90 # 緯度（北緯）
	return lat, lon

def pole2ratio(lon, lat, tile_coord):
    tile_lon,tile_lat = pole2tile(lon, lat, tile_coord[0])
    ratio_lon = (tile_lon - tile_coord[2])
    ratio_lat = (tile_lat - tile_coord[1])
    return ratio_lon, ratio_lat

def _download(tile_lon, tile_lat, zoom):
    url = f'https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{zoom}/{tile_lon}/{tile_lat}.pbf'
    title = os.path.dirname(__file__)+'/../data/test.pbf'
    urllib.request.urlretrieve(url,"{0}".format(title))
    url = f'https://cyberjapandata.gsi.go.jp/xyz/std/{zoom}/{tile_lon}/{tile_lat}.png'
    title = os.path.dirname(__file__)+'/../data/img.png'
    urllib.request.urlretrieve(url,"{0}".format(title))

def _nearest_node(dic, lat, lon):
    for i, key in enumerate(dic.keys()):
        l = (lat-dic[key]["coord"][0])**2 + (lon-dic[key]["coord"][1])**2
        if i == 0:
            min_l = l
            min_key = key
        
        if min_l > l:
            min_l = l
            min_key = key
    return int(min_key)

def _nearest_node_db(cur, table_name, lat, lon):
    cur.execute(f"SELECT * FROM {table_name}")
    nodes = cur.fetchall()
    
    for i, node in enumerate(nodes):
        l = (lat-node[6])**2 + (lon-node[7])**2
        if i == 0:
            min_l = l
            min_id = node[0]
        
        if min_l > l:
            min_l = l
            min_id = node[0]
        
    return int(min_id)

def _get_latlon_byname(name):
    googleapikey = 'AIzaSyAiNWxoEEoz4cD4dpXaNrpi0Df8nsKPDoA'
    gmaps = googlemaps.Client(key=googleapikey)
    result = gmaps.geocode(name)
    lat = result[0]['geometry']['location']['lat']
    lon = result[0]['geometry']['location']['lng']
    return lat, lon

def _weight(route, csr_link_matrix):
    matrix = csr_link_matrix.toarray()
    L = len(route)
    sum_w = 0
    for l in range(L):
        if l!=0:
            node = route[l]
            p_node = route[l-1]
            w = matrix[node, p_node]
            sum_w = sum_w + w

    return sum_w

class Plot_route():
    def __init__(self, config):

        tile_coord = (config["coord"]["zoom"], config["coord"]["t_lon"], config["coord"]["t_lat"])

        _download(tile_lon = tile_coord[1], tile_lat = tile_coord[2], zoom = tile_coord[0])

        self.img = cv2.imread('../data/img.png')
        h, w, c = self.img.shape
        self.img = cv2.resize(self.img, (h*3, w*3))

    def draw_plots(self, dic):
        h, w, c = self.img.shape
        for key in dic.keys():
            ratio_lon = dic[key]["ratio_coord"][0]
            ratio_lat = dic[key]["ratio_coord"][1]
            lon = int(ratio_lon*w)
            lat = int(ratio_lat*h)
            cv2.circle(self.img, (lon,lat), 1, (255,255,0), -1)

    def draw_lines(self, dic):
        h, w, c = self.img.shape
        for key in dic.keys():
            ratio_lon = dic[key]["ratio_coord"][0]
            ratio_lat = dic[key]["ratio_coord"][1]
            lon = int(ratio_lon*w)
            lat = int(ratio_lat*h)
            for neighbor in dic[key]["neighbors"]:
                n_ratio_lon = dic[neighbor]["ratio_coord"][0]
                n_ratio_lat = dic[neighbor]["ratio_coord"][1]
                n_lon = int(n_ratio_lon*w)
                n_lat = int(n_ratio_lat*h)
                cv2.line(self.img, (lat, lon), (n_lat, n_lon), (255,0,255), 1)
        self.draw_plots(dic)
        cv2.imwrite('../data/line_img.png', self.img)

    def draw_route(self, dic, route):
        h, w, c = self.img.shape
        self.draw_lines(dic)

        for i in range(len(route)):
            node = str(route[i])
            ratio_lon = dic[node]["ratio_coord"][0]
            ratio_lat = dic[node]["ratio_coord"][1]
            lon = int(ratio_lon*w)
            lat = int(ratio_lat*h)
            if i == 0:
                cv2.circle(self.img, (lat, lon), 10, (0, 0, 255), -1)
            elif i == len(route)-1:
                cv2.circle(self.img, (lat, lon), 10, (255, 0, 0), -1)
            else:
                node = str(route[i-1])
                ratio_lon = dic[node]["ratio_coord"][0]
                ratio_lat = dic[node]["ratio_coord"][1]
                plon = int(ratio_lon*w)
                plat = int(ratio_lat*h)
                cv2.line(self.img, (plat, plon), (lat, lon), (255,255,0), 2)
        cv2.imwrite('../data/route_img.png', self.img)

class Plot_route_db():
    def __init__(self, config):

        tile_coord = (config["coord"]["zoom"], config["coord"]["t_lon"], config["coord"]["t_lat"])

        _download(tile_lon = tile_coord[1], tile_lat = tile_coord[2], zoom = tile_coord[0])
        
        self.img = Image.open(os.path.dirname(__file__)+'/../data/img.png')
        h, w = self.img.size
        # self.img = self.img.resize((int(h*0.5), int(w*0.5))
        ratio = 1/30*2
        self.img = self.img.crop((-w*ratio, -w*ratio, w+w*ratio, h+h*ratio))
        # self.img = cv2.resize(self.img, (h*5, w*5))

    def draw_plots(self, cur, table_name):
        cur.execute(f"SELECT * FROM {table_name}") 
        nodes = cur.fetchall()
        w, h = self.img.size
        lats = []
        lons = []
        fig = plt.figure(figsize=(8, 6))
        # fig = Figure()
        ax = fig.add_subplot(1, 1, 1)

        for i, node in enumerate(nodes):
            lats.append(node[6])
            lons.append(node[7])
        ax.scatter(lons, lats, s = 1)
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        ax.imshow(self.img, extent=[*xlim, *ylim], alpha=0.6)
        plt.savefig('../data/plots_img.png')
        return fig, ax

    def draw_route(self, cur, table_name, route):
        fig, ax = self.draw_plots(cur, table_name)

        lats = []
        lons = []
        for i in range(len(route)):
            node = str(route[i])
            cur.execute(f"SELECT * FROM {table_name} where id = {node}") 
            node_data = cur.fetchone()
            lons.append(node_data[7])
            lats.append(node_data[6])
            if len(lats) > 1:
                ax.annotate('', xy=(lons[-1],lats[-1]), xytext=(lons[-2], lats[-2]),
                                arrowprops=dict(arrowstyle=ArrowStyle('<|-', head_length=0.3, head_width=0.15)))

            
        ax.scatter(lons, lats, s = 2)
        ax.plot(lons, lats, color='red')
        plt.savefig('../data/route_img.png')
        return fig, ax
    
    def draw_routes(self, cur, table_name, routes):
        self.draw_plots(cur, table_name)
        print(len(routes))
        for route in routes:
            self.draw_route(cur, table_name, route)
        plt.savefig(os.path.dirname(__file__)+'/../data/routes_img.png')
