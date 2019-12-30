#!/usr/bin/env python

import base64
import datetime
import json
# import os
import requests
import shutil
import numpy as np
import pandas as pd
import xarray as xr
import sys
import os

# %%

fildir = '/sand/usgs/users/dnowacki/wind/'

def fetch_api_data(params):

    s = requests.Session()

    r = s.get('https://dashboard.hologram.io/api/1/csr/rdm', params=params)

    lines = []
    for n in range(len(r.json()['data'])):
        lines.append(base64.b64decode(json.loads(r.json()['data'][n]['data'])['data']).decode('utf-8').split(','))

    while r.json()['continues']:
        r = s.get('https://dashboard.hologram.io' + r.json()['links']['next'])
        print('appending lines', lines[-1])
        for n in range(len(r.json()['data'])):
            lines.append(base64.b64decode(json.loads(r.json()['data'][n]['data'])['data']).decode('utf-8').split(','))

    return lines

if len(sys.argv) == 1:
    site = 'gri'
else:
    site = sys.argv[1]

print(site)

deviceid = {'gri': '511833'}

timestart = {'gri': 1576108800}

params = {}
with open('hologram.apikey') as f:
    params['apikey'] = f.read().strip()
params['deviceid'] = deviceid[site]
params['timestart'] = timestart[site]

lines = fetch_api_data(params)
# %%
df = pd.DataFrame([dict(zip(l[0::2], l[1::2])) for l in lines])
df['time'] = pd.DatetimeIndex(df['time'])
df.set_index('time', inplace=True)
df.columns

for k in df.columns:
    df[k] = pd.to_numeric(df[k])

ds = df.to_xarray().sortby('time')
# ds['time'] = pd.DatetimeIndex(ds['time'].values)
ds['time'] = pd.DatetimeIndex(ds['time'].values)


for k in ds.data_vars:
    ds[k][ds[k] == -9999] = np.nan

ds = ds.drop('sample')

ds.attrs['title'] = 'Test Meteorological Station. PROVISIONAL DATA SUBJECT TO REVISION.'
ds.attrs['history'] = 'Generated using vaisala-holo.py'

ds['latitude'] = xr.DataArray([36.959510], dims='latitude')
ds['longitude'] = xr.DataArray([-122.057024], dims='longitude')

ds['feature_type_instance'] = xr.DataArray(site)
ds['feature_type_instance'].attrs['long_name'] = 'station code'
ds['feature_type_instance'].attrs['cf_role'] = 'timeseries_id'

ds.attrs['naming_authority'] = 'gov.usgs.cmgp'
ds.attrs['original_folder'] = 'wind'
ds.attrs['featureType'] = 'timeSeries'
ds.attrs['cdm_timeseries_variables'] = 'feature_type_instance, latitude, longitude'

def add_standard_attrs(ds):
    ds.attrs['Conventions'] = 'CF-1.6'
    ds.attrs['institution'] = 'U.S. Geological Survey'

    ds['time'].attrs['standard_name'] = 'time'

    ds['Dm'].attrs['standard_name'] = 'wind_from_direction'
    ds['Dm'].attrs['units'] = 'degree'

    ds['Sm'].attrs['standard_name'] = 'wind_speed'
    ds['Sm'].attrs['units'] = 'm s-1'

    ds['Pa'].attrs['standard_name'] = 'air_pressure'
    ds['Pa'].attrs['units'] = 'Pa'

    ds['Ta'].attrs['standard_name'] = 'air_temperature'
    ds['Ta'].attrs['units'] = 'degree_C'

    ds['Ua'].attrs['standard_name'] = 'relative_humidity'
    ds['Ua'].attrs['units'] = 'percent'

    ds['Rc'].attrs['standard_name'] = 'rainfall_amount'
    ds['Rc'].attrs['units'] = 'mm'

    if 'signalpct' in ds:
        ds['signalpct'].attrs['units'] = 'percent'
        ds['signalpct'].attrs['long_name'] = 'Cellular signal strength'

    if 'boardbatt' in ds:
        ds['boardbatt'].attrs['units'] = 'V'
        ds['boardbatt'].attrs['long_name'] = 'Logger board battery voltage'

    if 'boardtemp' in ds:
        ds['boardtemp'].attrs['units'] = 'degree_C'
        ds['boardtemp'].attrs['long_name'] = 'Logger board temperature'

    if 'latitude' in ds:
        ds['latitude'].attrs['long_name'] = 'latitude'
        ds['latitude'].attrs['units'] = "degrees_north"
        ds['latitude'].attrs['standard_name'] = "latitude"
        ds['latitude'].encoding['_FillValue'] = None

    if 'longitude' in ds:
        ds['longitude'].attrs['long_name'] = 'longitude'
        ds['longitude'].attrs['units'] = "degrees_east"
        ds['longitude'].attrs['standard_name'] = "longitude"
        ds['longitude'].encoding['_FillValue'] = None

add_standard_attrs(ds)

ds = ds.squeeze()

# %%
# make a backup
timestr = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
try:
    shutil.copy(fildir + site + '.nc', fildir + '../wind_bak/' + site + timestr + '.nc')
except:
    print('Could not make backup. This may occur on first run')
ds.to_netcdf(fildir + site + '.nc', encoding={'time': {'dtype': 'int32'},
                                              'signalpct': {'dtype': 'int32'}})
