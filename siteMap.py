import pandas as pd
import numpy as np
import pydeck as pdk
import shapefile
import streamlit as st
import random 
from stqdm import stqdm
import geopy.distance

import os
import streamlit.components.v1 as components 

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
tabs = ["Анализ", "Строительство", "Инструкция"]
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



if active_tab == tabs[2]: #Раздел помощи
    help_text = open("README.md").readlines()
    st.markdown(help_text)
    st.stop()


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
b_types_array = ['','МФЦ','Школа','Торговый центр']


#создаём селект боксы и заголовки страницы
st.title('Проект команды "KOD в мешке"')

is_run_build = None
models_dict = {'Ничего':'','Точечная модель':'mfc_chance_agreg','Секторная модель':'mfc_chance_balance'}
models_descr = {'Ничего':'','Точечная модель':'Точечная модель позволяет оценивать локальную необходимость простройки учреждения','Секторная модель':'Строит сектора дочерник к учреждениям областей. Полезна для оценки производительности учреждений'}

if active_tab == tabs[0]: #анализ блок
    build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array, key='build_type')
    if build_type != '':
        show_mfc = (build_type != '') #st.sidebar.checkbox('Показать учреждения на карте', value=False)
        adm_zone = st.sidebar.selectbox('Выберите административную зону',np.concatenate(( [''],adm_names)), help = "Целевой район Москвы")
        model_type = st.sidebar.radio('Выберите модель расчётов',models_dict, key='model_type')
        st.sidebar.write(models_descr[model_type])
        print_all_btn = st.sidebar.checkbox('Вывести для всех регионов', value=(adm_zone== '') )
        hide_model = model_type == "Ничего"#st.sidebar.checkbox('Скрыть отображение модели?', value=False)
    else:
        show_mfc = False
        adm_zone = ''
        model_type = 'Ничего'
        print_all_btn = False
        hide_model = model_type == "Ничего"

elif active_tab == tabs[1]: #строительный блок
    print_all_btn = True
    #adm_zone = st.sidebar.selectbox('Выберите административную зону',adm_names, )
    show_mfc = True
    build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array, key='build_type')
    address = st.sidebar.text_input(f"Адрес будующего учреждения ({build_type})")
    windows_count = st.sidebar.number_input("Количество окон", value=20)
    model_type = st.sidebar.radio('Выберите модель расчётов',models_dict, key='model_type')
    st.sidebar.write(models_descr[model_type])
    hide_model = st.sidebar.checkbox('Скрыть отображение модели?', value=False)
    id_cell = int(st.sidebar.text_input("ID ячейки строительства", value=42400))
    if id_cell in c_locations['zid'].values:
        is_run_build = st.sidebar.button("Построить!")
    else:
        is_run_build = False
        st.sidebar.error(f"{id_cell} такой ячейки не существует!")
else:
    st.sidebar.error("Something has gone terribly wrong.")


model_key = models_dict[model_type]
st.sidebar.image('whiteCat.png', width=100)
#c_locations['adm_name'] = c_locations['zid'].apply(lambda x: loc_names.loc[x == loc_names['cell_zid']]['adm_name'].values[0])
#извлекаем ячейки выбранного в меню района Москвы
if print_all_btn:
    df = c_locations.copy()#.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]
else:
    df = c_locations.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]

#Выводим описание выбранного региона (население, площадь) и информацию 



mfc_df = mfc_info_df.copy() if print_all_btn else mfc_info_df.loc[mfc_info_df['global_id'].isin(df['nearest_mfc_id'])]

import re
mfc_df['geodata_center'] = mfc_df['geodata_center'].apply(lambda x: [float(coord) for coord in re.findall(r'[0-9]+\.[0-9]+', str(x))] )



map_widget = st.empty()

with st.spinner('Идёт просчёт, это займёт около 5 минут...') as spinner:
    message = st.empty()
    
    if is_run_build:
        id_cell = int(id_cell)
        neighbour_distance = 10 #km
        
        #print("Средняя необходимость по москве:", df[model_key].mean())
        import re
        mfc_df['geodata_center'] = mfc_df['geodata_center'].apply(lambda x: [float(coord) for coord in re.findall(r'[0-9]+\.[0-9]+', str(x))] )


        mfc_df['neighbour_mfc'] = mfc_df['global_id'].apply(lambda mfc_id: 
                                                                mfc_df.loc[mfc_df['geodata_center'].apply(
                                                                    lambda mfc_center: 
                                                                    geopy.distance.distance(
                                                                        mfc_center,
                                                                        mfc_df.loc[mfc_df['global_id']==mfc_id]['geodata_center']).km <= neighbour_distance)
                                                                ]['global_id'].values)

        array = mfc_df.loc[mfc_df['global_id'] == df.loc[df['zid']==id_cell]['nearest_mfc_id'].values[0]]['neighbour_mfc'].values[0]
        array = array.tolist()

        array.extend([-1])
        #print("до ",mfc_df.shape)
        mfc_df.loc[len(mfc_df)] = {"global_id":-1,       
                        "Address":address,          
                        "ShortName":f'{build_type} "Предварительный"',        
                        "WindowCount": int(40),      
                        "geodata_center":[float(df.loc[df['zid'] == id_cell]['lat'].values[0]),
                                          float(df.loc[df['zid'] == id_cell]['lon'].values[0])],
                        "lon":df.loc[df['zid'] == id_cell]['lat'].values[0],             
                        "lat":df.loc[df['zid'] == id_cell]['lon'].values[0],            
                        "District":"",
                        "metaInfo":"",
                        "neighbour_mfc":array,}

        #stqdm.pandas(desc = "Процесс повторного поиска учреждений")

        message.info("Процесс повторного поиска учреждений")
        target_cells = []
        for x in df['zid']:
            if df.loc[df['zid']==x]['nearest_mfc_id'].values[0] in mfc_df.loc[mfc_df['global_id'] == -1]['neighbour_mfc'].values[0]:
                target_cells.append(x)
        st.write(f'необходимо просчитать {len(target_cells)} ячеек')

        df['nearest_mfc_id'] = df['zid'].apply(
        lambda x: mfc_df.loc[mfc_df['geodata_center'].apply(
            lambda y: geopy.distance.distance((y[0],y[1]),
                            (float(df.loc[df['zid']==x]['lat'].values[0]),
                            float(df.loc[df['zid']==x]['lon'].values[0]))
                                        ).m
            ).idxmin()]['global_id'] if x in target_cells else df.loc[df['zid']==x]['nearest_mfc_id'].values[0])

        #stqdm.pandas(desc = "Рачёт дистанций до учреждений")
        message.info("Рачёт дистанций до учреждений")
        df['nearest_mfc_distance'] = -1
        df['nearest_mfc_distance'] = df['zid'].apply(
        lambda x: geopy.distance.distance(mfc_df.loc[mfc_df['global_id'] == df.loc[df['zid']==x]['nearest_mfc_id'].values[0]]['geodata_center'], 
                                        (df.loc[df['zid']==x]['lat'].values[0], df.loc[df['zid']==x]['lon'].values[0])).m)

        people_to_one_window = 3000
        summ_columns = ['customers_cnt_home','customers_cnt_job','customers_cnt_day'] #поля по которым будет осуществляться сумма плотности людей
        mfc_df['people_flow_rate'] = mfc_df['global_id'].apply(lambda x: df.loc[df['nearest_mfc_id'] == x][summ_columns].values.sum())
        mfc_df['max_people_flow'] = mfc_df['WindowCount'] * people_to_one_window 
        mfc_df['future_people_flow_rate'] = mfc_df['global_id'].apply(lambda x: df.loc[df['nearest_mfc_id'] == x][summ_columns].values.sum())


        message.info("Рачёт дистанций до учреждений")
        df['nearest_mfc_distance'] = -1
        df['nearest_mfc_distance'] = df['zid'].apply(
        lambda x: geopy.distance.distance(mfc_df.loc[mfc_df['global_id'] == df.loc[df['zid']==x]['nearest_mfc_id'].values[0]]['geodata_center'], 
                                        (df.loc[df['zid']==x]['lat'].values[0], df.loc[df['zid']==x]['lon'].values[0])).m)

        people_to_one_window = 3000
        summ_columns = ['customers_cnt_home','customers_cnt_job','customers_cnt_day'] #поля по которым будет осуществляться сумма плотности людей
        mfc_df['people_flow_rate'] = mfc_df['global_id'].apply(lambda x: df.loc[df['nearest_mfc_id'] == x][summ_columns].values.sum())
        mfc_df['max_people_flow'] = mfc_df['WindowCount'] * people_to_one_window 
        mfc_df['future_people_flow_rate'] = mfc_df['global_id'].apply(lambda x: df.loc[df['nearest_mfc_id'] == x][summ_columns].values.sum())

        st.dataframe(mfc_df)


        message.info("Процесс повторной прогонки модели")
        if model_key == 'mfc_chance_agreg':
            df[model_key] = 0

            #Настройка влияния весов на параметры плотности людей
            alphas = {'home':1.0,'job':1.0,'day':1.0, 'move':1.0}
            alphas_dlt = {'home':0.5,'job':0.5,'day':0.5, 'move':0.5}

            stqdm.pandas(desc="Перерасчёт точесной модели оптимизации")

            for feature in ['home', 'job', 'day', 'move']:
                df[model_key] = df[model_key] + alphas[feature] * df[f'customers_cnt_{feature}']
            for feature in ['home', 'job', 'day', 'move']:
                df[model_key] = df[model_key] + alphas_dlt[feature] *  df[f'customers_dlt_{feature}']  
                
            df[model_key] = df[model_key] + (df['nearest_mfc_distance'])# / 43617.48364582916)*1000
            df[model_key] = df[model_key] + (df['logistic'])

            df[model_key] = df[model_key].apply(lambda x: 1 + 5* x / 42070.344117)
        elif model_key == 'mfc_chance_balance':
            
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
            df[model_type] = df['nearest_mfc_id'].apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
            #Расчёт необходимости исходя из будущей загруженности
            df[model_type] = df[model_type] + 0.5 * df['nearest_mfc_id'].apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['future_people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
            #Расчёт необходимости исходя из удалённости 
            df[model_type] = df[model_type] +  df['nearest_mfc_distance'].apply(lambda x: coeff_distance(x / 1000.0) )
            #Расчёт необходимости исходя из логистики
            df[model_type] = df[model_type] +  (df['nearest_mfc_id'].apply(lambda x: coeff_logistic(df.loc[df['nearest_mfc_id'] == x]['logistic'].mean())) /  df['logistic']).apply(lambda x: coeff_logistic(x)) #
        else:
            st.error("Просчёт модели невозможет, ключ модели неверен!")

#Собираем шаблон подсказки для столбцов(ячеек) карты
message.empty()
mfc_df['metaInfo'] = "Краткое название: " + mfc_df['ShortName'] + \
                    "<br/>Адрес учреждения: " + mfc_df['Address'] + \
                    "<br/>Загруженность текущая/максимальная: " + mfc_df['people_flow_rate'].apply(str) + "/" + mfc_df['max_people_flow'].apply(str) + \
                    "<br/>Степень загруженности: " + (mfc_df['people_flow_rate']/ mfc_df['max_people_flow']).apply(lambda x: f"{x:.{3}f}") + " - " +  (mfc_df['people_flow_rate']/ mfc_df['max_people_flow']).apply(lambda x: get_assessment(x).lower())

#"<b>Ячейка района</b> " + df['adm_name'].apply(str) +\
df['metaInfo'] = "" + \
            "<br/><b>Насление</b> : " + df[['customers_cnt_home', 'customers_cnt_move']].sum(axis=1).apply(str)  +\
            "<br/><b>Прирост:</b> " + df[['customers_dlt_home', 'customers_dlt_move']].sum(axis=1).apply(str) + \
            "<br/><b>Логистика:</b> " + df['logistic'].apply(str) + \
            ("<br/><b>Необходимость постройки учреждения:</b> <br/>" + df[model_key].apply(lambda m: '🔴'*int(min(5,m))) + df[model_key].apply(lambda m: '⭕'*(5-int(m)))) if model_key != '' else '' + \
            "<br/><b>ID ячейки:</b> " + df['zid'].apply(str) + \
            "<br/><b>ID МФЦ:</b> " + df['nearest_mfc_id'].apply(str)
            

tooltip_template = '{metaInfo}'
if not hide_model and model_key != '':
    layers=[
        pdk.Layer("ScatterplotLayer", #слой для отображения колонок вероятности постройки учреждения
        data=df[['zid','lon', 'lat', 'metaInfo', model_key]],
        get_position='[lon,lat]',
        elevation = 1,# = "none",#=model_key,
        elevation_scale=0,
        get_radius=250,
        get_fill_color=[ f"{model_key} * 42 - 15",f"255-{model_key}*42",10,f"100+{model_key}*22"],# f"{model_key} * 42 - 15"],
        #get_border_color=[f"{model_key} * 42 - 15",f"255-{model_key}*42",20, 100],
        pickable=True,
        auto_highlight=True,
        )]
else:
    layers=[]

if show_mfc:

    layers.append(pdk.Layer("ColumnLayer", #слой для отображения уже существующих МФЦ
        data=mfc_df[['lon', 'lat', 'metaInfo']],
        get_position='[lat,lon]',
        elevation=100,#"WindowCount",
        elevation_scale=1,
        radius=50,
        get_fill_color=[1,1,255, 200],
        pickable=True,
        auto_highlight=True,    
        ))

#Инициализируем карту районов и известных учреждений
preview_lat = 55.752004
preview_lon = 37.617734
if is_run_build:
    preview_lat = df.loc[df['zid'] == id_cell]['lat'].values[0]
    preview_lon = df.loc[df['zid'] == id_cell]['lon'].values[0]

world_map = pdk.Deck(
    map_style=pdk.map_styles.ROAD,#'mapbox://styles/mapbox/light-v9',
    api_keys = {'mapbox':'pk.eyJ1Ijoic2hhcjE3MCIsImEiOiJja3ZrMHl1azAyYmVuMndxNTZmOWgyeG9yIn0._UpnTtbmZ7hxPU_Ff5SMRw'},
    map_provider='mapbox',
    initial_view_state=pdk.ViewState(latitude=preview_lat,longitude=preview_lon,zoom=11,pitch=50,),
     tooltip = {
        "html": tooltip_template,
        "style": {"backgroundColor": "black","color": "white"}
    },
    layers=layers,
)

#world_map.deck_widget.on_click()

click_code = """
let mapboxglMap = document.getElementById('deck-container').children[1]

mapboxglMap.onclick = async e => {
if (deckInstance._lastPointerDownInfo != null ) {
coords = await deckInstance._lastPointerDownInfo.object;
console.log(coords.lat, coords.lon);
window.open(`http://localhost:8501/?tab=Строительство&target_zid=${coords.zid}`);
}
}
"""
#let res = await axios.get(`http://localhost:8501/?tab=Строительство&target_zid=${coords.zid}`)

library_code = '<script src="https://cdnjs.cloudflare.com/ajax/libs/axios/0.24.0/axios.min.js" integrity="sha512-u9akINsQsAkG9xjc1cnGF4zw5TFDwkxuc9vUp5dltDWYCSmyd0meygbvgXrlc/z7/o4a19Fb5V0OUE58J7dcyw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>'



if active_tab == tabs[1]:
    random_file = f'{random.randint(10000,1000000)}_map.html'
    world_map.to_html(random_file)
    html_code = open(random_file).readlines()
    html_code.insert(62,click_code)
    html_code.insert(9,library_code)
    os.remove(random_file)
    #st.markdown(' '.join(html_code), unsafe_allow_html=True)
    components.html(' '.join(html_code), height=600)
elif active_tab == tabs[0]:
    map_widget.pydeck_chart(world_map)
#аналитикаЫ





def print_main_tooltip():
    global df,build_type
    if build_type != '':
        col1, col21, col22 = st.columns((1,2,2))
        col01, col02 = st.columns((1,6))
        col1.write(f"""
        🔴 - высокая потребность
        
        🟢 - низкая потребность

        🔵 - учреждения""")

        if print_all_btn or adm_zone == '':
            col02.write(f'''Вы выбрали всю Москву сейчас население в ней: {sum(df["customers_cnt_home"].values) + sum(df["customers_cnt_move"].values)} чел. на { df.shape[0]*0.25} км²''')
        else:
            col02.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(df["customers_cnt_home"].values) + sum(df["customers_cnt_move"].values)} чел. на { df.shape[0]*0.25} км²''')
            col22.metric("Проживающие кол-во", str(sum(df['customers_cnt_home'].values) + sum(df['customers_cnt_move'].values)) + " чел.", str(sum(df['customers_dlt_home'].values)+sum(df['customers_dlt_move'].values)) + " чел.")
            col22.metric("Работающие кол-во", str(sum(df['customers_cnt_job'].values)) + " чел.", str(sum(df['customers_dlt_job'].values)) + " чел.")
            col22.metric("Дневное кол-во", str(sum(df['customers_cnt_day'].values)) + " чел.", str(sum(df['customers_dlt_day'].values)) + " чел.")
    else:

        if print_all_btn or adm_zone == '':
            st.write(f'''Вы выбрали всю Москву сейчас население в ней: {sum(c_locations["customers_cnt_home"].values) + sum(c_locations["customers_cnt_move"].values)} чел. на { c_locations.shape[0]*0.25} км²''')
        else:
            st.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(c_locations["customers_cnt_home"].values) + sum(c_locations["customers_cnt_move"].values)} чел. на { c_locations.shape[0]*0.25} км²''')

        st.write('Выберите тип учреждений, для отображения базовой статистики')

print_main_tooltip()