from threading import current_thread
import pandas as pd
import numpy as np
import pydeck as pdk
import shapefile
import streamlit as st
import random 
from stqdm import stqdm
import geopy.distance

import master_block
import left_block

import altair as alt

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
st.title('Проект команды "KOD в мешке"')


query_params = st.experimental_get_query_params()

id_cell = 0
is_run_build = False


if "target_zid" in query_params:
    id_cell = query_params["target_zid"][0]
    if id_cell.isdigit():
        id_cell = int(id_cell)
        if "windows_count" in query_params:
            windows_count = query_params["windows_count"][0]
            if windows_count.isdigit():
                windows_count = int(windows_count)
                is_run_build = True 
                adm_zone = ''
                address = ''
                build_type = 'МФЦ'
                st.info(f"Начат расчёт в ячейке **{id_cell}**, для **МФЦ {windows_count}**(окон) это может занять 5-7 минут!")
else:
    tabs = left_block.tabs
    active_tab = left_block.show_tabs()



# if active_tab == tabs[2]: #Раздел помощи
#     help_text = open("README.md").readlines()
#     st.markdown(help_text)
#     st.stop()


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

@st.cache(allow_output_mutation=True)
def load_shp(shp_path, dbf_path):
    """
    Функция загрузки shape файла о разбиении на ячейки
    """
    #загружаем информацию о сеточном рабиении МО в память
    myshp = open(shp_path, "rb")
    mydbf = open(dbf_path, "rb")
    r = shapefile.Reader(shp=myshp, dbf=mydbf)
    return read_shapefile(r)
    #в поле coords первая координата центр квадрата, остальные его углы
s_df = load_shp("fishnet2021.shp", "fishnet2021.dbf")

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
    if percent < 1.5 and percent >=0.9: outstr = 'Высокая'
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
hider_model = 'Скрыть'
models_dict = {'Скрыть':'','Точечная модель':'mfc_chance_agreg','Отобразить':'mfc_chance_balance'}
models_dict_cutter = {'Скрыть':'','Отобразить':'mfc_chance_balance'}
models_descr = {hider_model:'','Точечная модель':'Точечная модель позволяет оценивать локальную необходимость простройки учреждения','Отобразить':'Строит сектора дочерник к учреждениям областей. Полезна для оценки производительности учреждений'}
model_help = ' **Математическая модель** - отображает сгруппированные точки в сектора по необходимости постройки учреждения.'

if not is_run_build:
    if active_tab == tabs[0]: #анализ блок
        build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array, key='build_type')
        if build_type != '':
            show_mfc = (build_type != '') #st.sidebar.checkbox('Показать учреждения на карте', value=False)
            adm_zone = st.sidebar.selectbox('Выберите административную зону',np.concatenate(( [''],adm_names)), help = "Целевой район Москвы")
            model_type = st.sidebar.radio('Модель расчётов',models_dict_cutter, key='model_type', help=model_help)
            if adm_zone != '' and model_type != hider_model:
                print_all_btn = False #st.sidebar.checkbox('Вывести для всех регионов', value=(adm_zone== '') )
                model_type = 'Точечная модель' if st.sidebar.checkbox('Уточнить место постройки', value = False, help='Выделяет точки с наивысшей степенью необходимости постойки, в данном районе') else model_type
            else:
                print_all_btn = True
                
            hide_model = model_type == "Ничего"#st.sidebar.checkbox('Скрыть отображение модели?', value=False)
        else:
            show_mfc = False
            adm_zone = ''
            model_type = hider_model
            print_all_btn = True
            hide_model = model_type == "Ничего"

    elif active_tab == tabs[1]: #строительный блок
        print_all_btn = True
        adm_zone = ""# = st.sidebar.selectbox('Выберите административную зону',adm_names, )
        show_mfc = True
        build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array, key='build_type')
        address = ''# st.sidebar.text_input(f"Адрес будующего учреждения ({build_type})")


        if build_type != '':
            adm_zone = st.sidebar.selectbox('Выберите административную зону',np.concatenate(( [''],adm_names)), help = "Целевой район Москвы")
            model_type = st.sidebar.radio('Выберите модель расчётов',models_dict_cutter, key='model_type', help=model_help)      
            
            if adm_zone != '' and model_type != hider_model:
                print_all_btn = False #st.sidebar.checkbox('Вывести для всех регионов', value=(adm_zone== '') )
                model_type = 'Точечная модель' if st.sidebar.checkbox('Уточнить место постройки', value = False, help='Выделяет точки с наивысшей степенью необходимости постойки в данном районе') else model_type
    
            if model_type != hider_model: 
                hide_model = False#st.sidebar.checkbox('Скрыть отображение модели?', value=False)
                if build_type == 'МФЦ':
                    windows_count = st.sidebar.number_input("Количество окон", value=20)
                if build_type == 'Школа':
                    windows_count = st.sidebar.number_input("Количество преподавателей", value=20)
                if build_type == 'Торговый центр':
                    windows_count = st.sidebar.number_input("Предполагаемая проходимость людей в день", value=2000)
                st.sidebar.write(f'**Двойный кликом** выберите ячейку, чтобы построить в ней "{build_type}"')
            else:
                hide_model = True
                st.sidebar.write(f'Для начала выберите одну из математических моделей ')# "{build_type}"')

            is_run_build = False
            #     st.sidebar.error(f"{id_cell} такой ячейки не существует!")
        else:
            show_mfc = False
            adm_zone = ''
            model_type = hider_model
            print_all_btn = True
            hide_model = True

    else:
        st.sidebar.error("Something has gone terribly wrong.")


model_key = models_dict[model_type] if not is_run_build else 'mfc_chance_balance'
st.sidebar.image('whiteCat.png', width=100)
#извлекаем ячейки выбранного в меню района Москвы

if adm_zone == '':
    df = c_locations.copy()#.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]
else:
    df = c_locations.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]

#Выводим описание выбранного региона (население, площадь) и информацию 



mfc_df = mfc_info_df.copy() if adm_zone == '' else mfc_info_df.loc[mfc_info_df['global_id'].isin(df['nearest_mfc_id'])]

import re
mfc_df['geodata_center'] = mfc_df['geodata_center'].apply(lambda x: [float(coord) for coord in re.findall(r'[0-9]+\.[0-9]+', str(x))] )

map_widget = st.empty()

message = st.empty()

if is_run_build:
    with st.spinner('Идёт просчёт, это займёт около 5 минут...') as spinner:
    
        #id_cell = int(id_cell)
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
        #st.write(f'необходимо просчитать {len(target_cells)} ячеек')

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
        else:
            
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
            df[model_key] = df['nearest_mfc_id'].apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
            #Расчёт необходимости исходя из будущей загруженности
            df[model_key] = df[model_key] + 0.5 * df['nearest_mfc_id'].apply(lambda x: coeff_flow(mfc_df.loc[mfc_df['global_id'] == x]['future_people_flow_rate'].values[0] / mfc_df.loc[mfc_df['global_id'] == x]['max_people_flow'].values[0]) )
            #Расчёт необходимости исходя из удалённости 
            df[model_key] = df[model_key] +  df['nearest_mfc_distance'].apply(lambda x: coeff_distance(x / 1000.0) )
            #Расчёт необходимости исходя из логистики
            df[model_key] = df[model_key] +  (df['nearest_mfc_id'].apply(lambda x: coeff_logistic(df.loc[df['nearest_mfc_id'] == x]['logistic'].mean())) /  df['logistic']).apply(lambda x: coeff_logistic(x)) #

        sizeDataset = 7
        max_flowrate = mfc_df.loc[mfc_df['global_id'] == -1]['max_people_flow'].values[0]
        current_flowrate = mfc_df.loc[mfc_df['global_id'] == -1]['people_flow_rate'].values[0]
        future_flowrate = mfc_df.loc[mfc_df['global_id'] == -1]['future_people_flow_rate'].values[0]
        flowRate = np.array([random.randint(current_flowrate*0.7,current_flowrate*1.3) for x in range(sizeDataset)])
        mfc_history = pd.DataFrame(data= {'date': [x for x in range(2017,2022)], 
                                        'people_flow_rate' : flowRate, 
                                        'strain': flowRate/max_flowrate})
        base = alt.Chart(mfc_history).encode(
                x = alt.X("date",    title='Год' ),
            ).properties (
            width = 1000
            )
        bars = base.mark_bar(size = 20).encode(y = alt.Y("people_flow_rate", title='Поток людей'),).properties (width = 1000)
        line = base.mark_line(strokeWidth= 1.5,color = "red").encode(y=alt.Y('strain',title='Справляемость',axis=alt.Axis()),text = alt.Text('strain'),)
        points = line.mark_circle(color='#00CED1',).encode(y=alt.Y('strain', axis=None))
        points_text = base.mark_text(color='#00CED1',align='left',baseline='middle',dx=-10,dy=-10,).encode(y=alt.Y('strain', axis=None),text=alt.Text('strain'),)
        charts = (bars +  line + points + points_text).resolve_scale(y = 'independent')
        st.altair_chart(charts)
        predic_text = ''
        if future_flowrate > max_flowrate:
            predic_text = f'Предполагается что в будущем нагрузка на построенное учредение будет расти, рекомендуется увеличить количество окон до: {int(1.5 * future_flowrate / people_to_one_window)}'
        else:
            predic_text = f'Предполагается что в близжайшем будущем нагрузка на построенное учредение не вырастет значительно, текущее количество окон даст достаточную справляемость'#
        
        st.write('Выводы прогноза: ', predic_text)

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
        

if is_run_build:
    preview_lat = df.loc[df['zid'] == id_cell]['lat'].values[0]
    preview_lon = df.loc[df['zid'] == id_cell]['lon'].values[0]
elif len(df) > 0 and not print_all_btn:
    preview_lat = df['lat'].values[0]
    preview_lon = df['lon'].values[0]
else:
    preview_lat = 55.752004
    preview_lon = 37.617734

#аналитика
col_map, col_tooltip = st.columns((5,1))

master_block.show_map(small_dataset=df,
                        mfc_df=mfc_df,
                        hide_model=hide_model, 
                        model_key=model_key , 
                        adm_zone=adm_zone , 
                        show_mfc=show_mfc,
                        preview_lat=preview_lat,
                        preview_lon=preview_lon,
                        as_html = active_tab == tabs[1],
                        map_container=col_map)


master_block.print_main_tooltip(df, c_locations,adm_zone,print_all_btn, metrics_column =col_tooltip )