"""Fixed sources and population; values are conventions, not fitted choices."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATES=['ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN']
TYPES=['Flash Flood','Flood','Hail','Thunderstorm Wind','Tornado']
YEARS=list(range(2015,2024))
FILES={2015:'20260323',2016:'20260323',2017:'20260519',2018:'20260323',2019:'20260323',2020:'20260323',2021:'20260323',2022:'20260625',2023:'20260323'}
FIELDS=['EPISODE_ID','EVENT_ID','STATE','YEAR','BEGIN_YEARMONTH','EVENT_TYPE','CZ_TYPE','WFO','DAMAGE_PROPERTY']
BASE_URL='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
ABSOLUTE,RELATIVE=1e-7,1e-9
REPLICATES,SEED=1000,20261029
