import pandas as pd
import numpy as np
import pydeck as pdk
import shapefile
import streamlit as st
import random 
from stqdm import stqdm
import geopy.distance

#инициализация параметров страницы
st.set_page_config(
    page_title="KOD в мешке App",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Проект КОД в мешке. *Рекомендательная система* для поиска наиболее оптимального построения раличных соц. учреждений! Наш GitHub: https://github.com/Shar170/KOD_v_meshke_MOS"
    }
    )


st.sidebar.markdown(
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css" integrity="sha384-TX8t27EcRE3e/ihU7zmQxVncDAy5uIKz4rEkgIXeMed4M0jlfIDPvg6uqKI2xXr2" crossorigin="anonymous">',
    unsafe_allow_html=True,)

query_params = st.experimental_get_query_params()
tabs = ["Анализ", "Строительство"]
if "tab" in query_params:
    active_tab = query_params["tab"][0]
else:
    active_tab = tabs[0]

if active_tab not in tabs:
    st.experimental_set_query_params(tab=tabs[0])
    active_tab = tabs[0]

li_items = "".join(
    f"""
    <li class="nav-item">
        <a class="nav-link{' active' if t==active_tab else ''}" href="/?tab={t}">{t}</a>
    </li>
    """
    for t in tabs
)
tabs_html = f"""
    <ul class="nav nav-tabs">
    {li_items}
    </ul>
"""

st.sidebar.markdown(tabs_html, unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)



def read_shapefile(sf_shape):
    """
    Read a shapefile into a Pandas dataframe with a 'coords' 
    column holding the geometry information. This uses the pyshp
    package
    """
    fields = [x[0] for x in sf_shape.fields][1:]
    records = [y[:] for y in sf_shape.records()]
    #records = sf_shape.records()
    shps = [s.points for s in sf_shape.shapes()]
    df = pd.DataFrame(columns=fields, data=records)
    df = df.assign(coords=shps)
    return df

@st.cache
def load_shp():
    """
    Функция загрузки shape файла о разбиении на ячейки
    """
    #загружаем информацию о сеточном рабиении МО в память
    myshp = open("fishnet2021.shp", "rb")
    mydbf = open("fishnet2021.dbf", "rb")
    r = shapefile.Reader(shp=myshp, dbf=mydbf)
    return read_shapefile(r)
    #в поле coords первая координата центр квадрата, остальные его углы
s_df = load_shp()

@st.cache
def load_h_w():
    """
    Функция загрузки логистической информации о переходах Дом-Работа 
    """
    #считываем информацию о переходах Дом-Работа и прикручиваем туда координаты переходов
    h_w_matrix = pd.read_csv("04_CMatrix_Home_Work_July.csv")
    h_w_matrix = h_w_matrix.merge(right=s_df, how='inner', left_on='home_zid', right_on='cell_zid')
    h_w_matrix = h_w_matrix.merge(right=s_df, how='inner', left_on='work_zid', right_on='cell_zid')
    h_w_matrix.drop('cell_zid_x', axis=1, inplace=True)
    h_w_matrix.drop('cell_zid_y', axis=1, inplace=True)
    return h_w_matrix

def load_names():
    """ 
    Функция для считывания наименований всех регинов и их координат
    """
    loc_names = pd.read_csv('rebuilded_names.csv')
    return loc_names.merge(right=s_df, how='inner', left_on='cell_zid', right_on='cell_zid')

def load_loc_info():
    """
    Функция для считывания информации о плотности проживающего, работающего и проходящего населения для каждого квадрата
    """
    c_locations = pd.read_csv("june_full_data.csv")
    
    # c_locations['mfc_chance'] = c_locations['mfc_chance'].apply(lambda m: '⭐'*int(m))
    return c_locations

@st.cache
def get_unic_names():
    return  pd.read_csv('rebuilded_names.csv')['adm_name'].drop_duplicates(inplace=False).values

def get_assessment(percent):
    outstr = ""
    if percent < 0.5:                   outstr = 'Очень низкая'
    if percent < 0.8 and percent >=0.5: outstr = 'Низкая'
    if percent < 0.9 and percent >=0.8: outstr = 'Средняя'
    if percent < 1.2 and percent >=0.9: outstr = 'Высокая'
    if percent > 1.5:                   outstr = 'Очень высокая'
    return outstr

def load_mfc_info():
    """
    Функция считывания информации о построенных МФЦ
    """
    mfc = pd.read_csv("mos_coords.csv")
    mfc['District'] = mfc['District'].apply(lambda x: x.replace('район', '').strip())
    mfc['metaInfo'] = "Краткое название: " + mfc['ShortName'] + \
                    "<br/>Адрес учреждения: " + mfc['Address'] + \
                    "<br/>Загруженность текущая/максимальная: " + mfc['people_flow_rate'].apply(str) + "/" + mfc['max_people_flow'].apply(str) + \
                    "<br/>Степень загруженности: " + (mfc['people_flow_rate']/ mfc['max_people_flow']).apply(lambda x: f"{x:.{3}f}") + " - " +  (mfc['people_flow_rate']/ mfc['max_people_flow']).apply(lambda x: get_assessment(x).lower())
    return mfc

#инициализируем и подгружаем все датасеты
loc_names = load_names()
c_locations = load_loc_info()
adm_names = get_unic_names()
mfc_info_df = load_mfc_info()
b_types_array = ['МФЦ','Школа','Торговый центр']


#создаём селект боксы и заголовки страницы
st.title('Проект команды "KOD в мешке"')

is_run_build = None
models_dict = {'Точечная модель':'mfc_chance_agreg','Секторная модель':'mfc_chance_balance'}
models_descr = {'Точечная модель':'Точечная модель позволяет оценивать локальную необходимость простройки учреждения','Секторная модель':'Строит сектора дочерник к учреждениям областей. Полезна для оценки производительности учреждений'}

if active_tab == tabs[0]: #анализ блок
    adm_zone = st.sidebar.selectbox('Выберите административную зону',adm_names, )
    print_all_btn = st.sidebar.checkbox('Вывести для всех регионов', value=False)
    build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array)
    show_mfc = st.sidebar.checkbox('Показать учреждения на карте', value=False)
    model_type = st.sidebar.selectbox('Выберите модель расчётов',models_dict)
    st.sidebar.write(models_descr[model_type])
elif active_tab == tabs[1]: #строительный блок
    print_all_btn = True
    show_mfc = True
    build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array)
    address = st.sidebar.text_input(f"Адрес будующего учреждения ({build_type})")
    windows_count = st.sidebar.text_input("Количество окон", value=20)
    model_type = st.sidebar.selectbox('Выберите модель расчётов',models_dict)
    st.sidebar.write(models_descr[model_type])
    id_cell = st.sidebar.text_input("ID ячейки строиткльства", value=95664)

    is_run_build = st.sidebar.button("Построить!")
else:
    st.sidebar.error("Something has gone terribly wrong.")


model_key = models_dict[model_type]
st.sidebar.image('whiteCat.png', width=100)

#извлекаем ячейки выбранного в меню района Москвы
if print_all_btn:
    df = c_locations.copy()#.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]
else:
    df = c_locations.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]

#Выводим описание выбранного региона (население, площадь) и информацию 

if print_all_btn:
    st.write(f'''Вы выбрали всю Москву сейчас население в ней: {sum(df["customers_cnt_home"].values) + sum(df["customers_cnt_move"].values)} чел. на { df.shape[0]*0.25} км²''')
else:
    st.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(df["customers_cnt_home"].values) + sum(df["customers_cnt_move"].values)} чел. на { df.shape[0]*0.25} км²''')

st.write(f'🔴 Красные области - места с высокой потребностью в учреждениях типа "{build_type}"')
st.write(f'🟢 Зелёнык области - места с низкой потребностью в учреждениях типа "{build_type}"')
st.write(f'🔵 Синие области - существующие на текущий момент учреждения типа "{build_type}"')

#Собираем шаблон подсказки для столбцов(ячеек) карты
df['metaInfo'] = "Насление: " + df[['customers_cnt_home', 'customers_cnt_move']].sum(axis=1).apply(str) +\
                            "<br/><b>Прирост:</b> " + df[['customers_dlt_home', 'customers_dlt_move']].sum(axis=1).apply(str) + \
                            "<br/><b>Логистика:</b> " + df['logistic'].apply(str) + \
                            "<br/><b>Необходимость постройки учреждения:</b> <br/>" + df[model_key].apply(lambda m: '🔴'*int(m)) + df[model_key].apply(lambda m: '⭕'*(5-int(m)))

mfc_df = mfc_info_df.copy() if print_all_btn else mfc_info_df.loc[mfc_info_df['global_id'].isin(df['nearest_mfc_id'])]

import re
mfc_df['geodata_center'] = mfc_df['geodata_center'].apply(lambda x: tuple(map(float, re.findall(r'[0-9]+\.[0-9]+', str(x)))))


world_map = st.empty()

if is_run_build:
    id_cell = int(id_cell)
    mfc_df.loc[len(df)] = {"global_id ":-1.0,       
                            "Address":address,          
                            "ShortName":f'{build_type} "Предварительный"',        
                            "WindowCount":windows_count,      
                            'geodata_center':(float(df.loc[df['zid'] == id_cell]['lon'].values[0]),float(df.loc[df['zid'] == id_cell]['lat'].values[0])),
                            "lon":df.loc[df['zid'] == id_cell]['lon'].values[0],             
                            "lat":df.loc[df['zid'] == id_cell]['lat'].values[0],            
                            "District":"",
                            "metaInfo":"",}
    

    st.dataframe(df.head())

    stqdm.pandas(desc = "Процесс повторного поиска учреждений")
    df['nearest_mfc_id'] = 0
    df['nearest_mfc_id'] = df['zid'].progress_apply(
    lambda x: mfc_df.loc[mfc_df['geodata_center'].apply(
        lambda y: geopy.distance.distance((y[0],y[1]),
                          (float(df.loc[df['zid']==x]['lat'].values[0]),
                           float(df.loc[df['zid']==x]['lon'].values[0]))
                                    ).m
        ).idxmin()]['global_id'])

    stqdm.pandas(desc = "Рачёт дистанций до учреждений")
    df['nearest_mfc_distance'] = -1
    df['nearest_mfc_distance'] = df['zid'].progress_apply(
    lambda x: geopy.distance.distance(mfc_df.loc[mfc_df['global_id'] == df.loc[df['zid']==x]['nearest_mfc_id'].values[0]]['geodata_center'], 
                                    (df.loc[df['zid']==x]['lat'].values[0], df.loc[df['zid']==x]['lon'].values[0])).m)



    mfc_df['metaInfo'] = "Краткое название: " + mfc_df['ShortName'] + \
                    "<br/>Адрес учреждения: " + mfc_df['Address'] + \
                    "<br/>Загруженность текущая/максимальная: " + mfc_df['people_flow_rate'].apply(str) + "/" + mfc_df['max_people_flow'].apply(str) + \
                    "<br/>Степень загруженности: " + (mfc_df['people_flow_rate']/ mfc_df['max_people_flow']).apply(lambda x: f"{x:.{3}f}") + " - " +  (mfc_df['people_flow_rate']/ mfc_df['max_people_flow']).apply(lambda x: get_assessment(x).lower())

    stqdm.pandas(desc = "Процесс повторной прогонки модели")
    if model_type == 'mfc_chance_agreg':
        df[model_type] = 0

        #Настройка влияния весов на параметры плотности людей
        alphas = {'home':1.0,'job':1.0,'day':1.0, 'move':1.0}
        alphas_dlt = {'home':0.5,'job':0.5,'day':0.5, 'move':0.5}

        stqdm.pandas(desc="Перерасчёт точесной модели оптимизации")

        for feature in ['home', 'job', 'day', 'move']:
            df[model_type] = df[model_type] + alphas[feature] * df[f'customers_cnt_{feature}']
        for feature in ['home', 'job', 'day', 'move']:
            df[model_type] = df[model_type] + alphas_dlt[feature] *  df[f'customers_dlt_{feature}']  
            
        df[model_type] = df[model_type] + (df['nearest_mfc'])# / 43617.48364582916)*1000
        df[model_type] = df[model_type] + (df['logistic'])

        df[model_type] = df[model_type].progress_apply(lambda x: 1 + 5* x / 42070.344117)
    else :
        
        def coeff_flow(percent):
            input_arr = [0.75,0.95,1.1,1.5,5]
            output_arr = [0.3,0.7,1.3,2,2]
            return np.interp(percent, input_arr, output_arr, left=0.0, right=2.0)

        def coeff_distance(km_dist):
            input_arr = [2,3.5,5]
            output_arr = [0.3,0.7,1.0]
            return np.interp(km_dist, input_arr, output_arr, left=0.0,right=1.0)

        def coeff_logistic(log_persent):
            input_arr = [0.5,1,1.5]
            output_arr = [0.3,0.5,1.0,]
            return np.interp(log_persent, input_arr, output_arr, left=0.0,right=1.0)
    
        #Расчёт необходимости исходя из текущей загруженности
        df[model_type] = df['nearest_mfc_id'].progress_apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
        #Расчёт необходимости исходя из будущей загруженности
        mfc_df['future_people_flow_rate'] = mfc_df['global_id'].progress_apply(lambda x: df.loc[df['nearest_mfc_id'] == x][summ_columns].values.sum())
        summ_columns = ['customers_cnt_home','customers_cnt_job','customers_cnt_day'] #поля по которым будет осуществляться сумма плотности людей
        df[model_type] = df[model_type] + 0.5 *   df['nearest_mfc_id'].progress_apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['future_people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
        #Расчёт необходимости исходя из удалённости 
        df[model_type] = df[model_type] +  df['nearest_mfc_distance'].progress_apply(lambda x: coeff_distance(x / 1000.0) )
        #Расчёт необходимости исходя из логистики
        df[model_type] = df[model_type] +  (df['nearest_mfc_id'].progress_apply(lambda x: coeff_logistic(df.loc[df['nearest_mfc_id'] == x]['logistic'].mean())) /  df['logistic']).apply(lambda x: coeff_logistic(x)) #





tooltip_template = '{metaInfo}'
layers=[
    pdk.Layer("ColumnLayer", #слой для отображения колонок вероятности постройки учреждения
    data=df,
    get_position='[lon,lat]',
    get_elevation=model_key,
    elevation_scale=200,
    radius=250,
    get_fill_color=[f"{model_key} * 42 - 15",f"255-{model_key}*42",20, 255],
    pickable=True,
    auto_highlight=True,
    )]





if show_mfc:

    layers.append(pdk.Layer("ColumnLayer", #слой для отображения уже существующих МФЦ
        data=mfc_df,
        get_position='[lat,lon]',
        elevation=100,#"WindowCount",
        elevation_scale=1,
        radius=50,
        get_fill_color=[1,1,255, 200],
        pickable=True,
        auto_highlight=True,    
        ))

#Инициализируем карту районов и известных учреждений
preview_lat = df['lat'].values[0]
preview_lon = df['lon'].values[0]
if is_run_build:
    preview_lat = df.loc[df['zid'] == id_cell]['lat'].values[0]
    preview_lon = df.loc[df['zid'] == id_cell]['lon'].values[0]

world_map = pdk.Deck(
    map_style='mapbox://styles/mapbox/light-v9',
    initial_view_state=pdk.ViewState(latitude=preview_lat,longitude=preview_lon,zoom=11,pitch=50,),
     tooltip = {
        "html": tooltip_template,
        "style": {"backgroundColor": "black","color": "white"}
    },
    layers=layers,
)

map_widget = st.pydeck_chart(world_map)


#аналитика

col1, col2, col3 = st.columns(3)
col1.metric("Проживающие кол-во", str(sum(df['customers_cnt_home'].values) + sum(df['customers_cnt_move'].values)) + " чел.", str(sum(df['customers_dlt_home'].values)+sum(df['customers_dlt_move'].values)) + " чел.")
col2.metric("Работающие кол-во", str(sum(df['customers_cnt_job'].values)) + " чел.", str(sum(df['customers_dlt_job'].values)) + " чел.")
col3.metric("Дневное кол-во", str(sum(df['customers_cnt_day'].values)) + " чел.", str(sum(df['customers_dlt_day'].values)) + " чел.")
