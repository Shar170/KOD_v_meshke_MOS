import pandas as pd
import numpy as np
import pydeck as pdk
import shapefile
import streamlit as st

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

def load_mfc_info():
    """
    Функция считывания информации о построенных МФЦ
    """
    mfc = pd.read_csv("mos_coords.csv")
    mfc['District'] = mfc['District'].apply(lambda x: x.replace('район', '').strip())
    mfc['metaInfo'] = "Краткое название: " + mfc['ShortName'] + \
                    "<br/>Адрес учреждения: " + mfc['Address'] + \
                    "<br/>Текущая загруженность: " + mfc['people_flow_rate'].apply(str) + \
                    "<br/>Максимально возможная загруженность: " + mfc['max_people_flow'].apply(str)
    return mfc

#инициализируем и подгружаем все датасеты
loc_names = load_names()
c_locations = load_loc_info()
adm_names = get_unic_names()
mfc_info_df = load_mfc_info()
b_types_array = ['МФЦ','Школа','Торговый центр']



#создаём селект боксы и заголовки страницы
st.title('Проект команды "KOD в мешке"')
adm_zone = st.sidebar.selectbox('Выберите административную зону',adm_names, )
print_all_btn = st.sidebar.checkbox('Вывести для всех регионов', value=False)
build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array)
show_mfc = st.sidebar.checkbox('Показать учреждения на карте', value=False)
models_dict = {'Агрегационная модель':'mfc_chance_agreg','Балансовая модель':'mfc_chance_balance'}
model_type = st.sidebar.selectbox('Выберите модель расчётов',models_dict)
st.sidebar.image('whiteCat.png', width=100)


model_key = models_dict[model_type]

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
        data=mfc_info_df if print_all_btn else mfc_info_df.loc[mfc_info_df['global_id'].isin(df['nearest_mfc_id'])],
        get_position='[lat,lon]',
        elevation=100,#"WindowCount",
        elevation_scale=1,
        radius=50,
        get_fill_color=[1,1,255, 200],
        pickable=True,
        auto_highlight=True,    
        ))


#Инициализируем карту районов и известных учреждений
world_map = pdk.Deck(
    map_style='mapbox://styles/mapbox/light-v9',
    initial_view_state=pdk.ViewState(latitude=df['lat'].values[0],longitude=df['lon'].values[0],zoom=11,pitch=50,),
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



st.write('Табличное представление загруженных данных')
st.dataframe(c_locations)
#st.dataframe(loc_names)
#st.dataframe(s_df)
#st.dataframe(h_w_matrix)