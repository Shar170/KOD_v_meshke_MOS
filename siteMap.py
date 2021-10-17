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


#функция чтения shape файла с размерами и координатами сетки райнов
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
    #загружаем информацию о сеточном рабиении МО в память
    myshp = open("fishnet2021.shp", "rb")
    mydbf = open("fishnet2021.dbf", "rb")
    r = shapefile.Reader(shp=myshp, dbf=mydbf)
    return read_shapefile(r)
    #в поле coords первая координата центр квадрата, остальные его углы
s_df = load_shp()


@st.cache
def load_h_w():
    #считываем информацию о переходах Дом-Работа и прикручиваем туда координаты переходов
    h_w_matrix = pd.read_csv("04_CMatrix_Home_Work_July.csv")
    h_w_matrix = h_w_matrix.merge(right=s_df, how='inner', left_on='home_zid', right_on='cell_zid')
    h_w_matrix = h_w_matrix.merge(right=s_df, how='inner', left_on='work_zid', right_on='cell_zid')
    h_w_matrix.drop('cell_zid_x', axis=1, inplace=True)
    h_w_matrix.drop('cell_zid_y', axis=1, inplace=True)
    return h_w_matrix


#@st.cache
def load_names():
    #считываем наименование всех регинов и прикручиваем к ним их координаты
    loc_names = pd.read_csv('rebuilded_names.csv')
    return loc_names.merge(right=s_df, how='inner', left_on='cell_zid', right_on='cell_zid')

#@st.cache
def load_loc_info():
    #считываем информацию о плотности проживающего, работающего и проходящего населения для каждого квадрата и прикручиваем туда координаты квадратов
    c_locations = pd.read_csv("june_full_data.csv")
    return c_locations
@st.cache
def get_unic_names():
    return  pd.read_csv('rebuilded_names.csv')['adm_name'].drop_duplicates(inplace=False).values


def load_mfc_info():
    #считываем информацию о плотности проживающего, работающего и проходящего населения для каждого квадрата и прикручиваем туда координаты квадратов
    mfc = pd.read_csv("mos_coords.csv")
    return mfc

#инициализируем и подгружаем все датасеты
loc_names = load_names()
c_locations = load_loc_info()
#h_w_matrix = load_h_w()
adm_names = get_unic_names()
mfc_info_df = load_mfc_info()

#st.dataframe(mfc_info_df.head())

st.title('Проект команды "KOD в мешке"')

st.write('Карта Москвы и МО. Круги отображают выбранный вами район')
b_types_array = ['МФЦ','Школа','Торговый центр']

adm_zone = st.sidebar.selectbox('Выберите административную зону',adm_names, )
print_all_btn = st.sidebar.checkbox('Вывести для всех регионов', value=False)
build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array)
show_mfc = st.sidebar.checkbox('Показать учреждения на карте', value=False)
filter_dict = {'Кол-во живущих':'home','Кол-во работающих':'job','Кол-во проходящях':'move','Логистика':'logistic'}
filter_type = st.sidebar.selectbox('Выберите оценочный фактор',filter_dict)
filter_value = st.sidebar.slider('Выберите степень влияния фактора', value=1.0, min_value=0.0, max_value=5.0, step=0.05)
#press_button = st.sidebar.button("Do magic!")
st.sidebar.image('whiteCat.png', width=100)

filter_key = filter_dict[filter_type]

c_locations['mfc_chance'] = 0

#Настройки влияния весов на параметры плотности людей
alphas = {'home':1.0,'job':1.0,'day':1.0, 'move':1.0}
alphas_dlt = {'home':0.5,'job':0.5,'day':0.5, 'move':0.5}

#Расчитываем оценку необходимости постройки учреждения
for feature in ['home', 'job', 'day', 'move']:#обрабатываем счётчики плотности за текущий месяц
    c_locations['mfc_chance'] = c_locations['mfc_chance'] + (filter_value if filter_key == feature else (1.0)) * alphas[feature] * c_locations[f'customers_cnt_{feature}']
for feature in ['home', 'job', 'day', 'move']:#обрабатываем дельты измения плотностей
    c_locations['mfc_chance'] = c_locations['mfc_chance'] + (filter_value if filter_key == feature else  (1.0)) * alphas_dlt[feature] *  c_locations[f'customers_dlt_{feature}']  

#инкрементация шанса за счёт большой удалённости от других учреждений
c_locations['mfc_chance'] = c_locations['mfc_chance'] + (c_locations['nearest_mfc'])
#инкрементация шанс за счёт высокой логичтики внутри ячейки
c_locations['mfc_chance'] = c_locations['mfc_chance'] + (filter_value if filter_key == 'logistic' else  (1.0)) * (c_locations['logistic'])
#нормирование шанса 
c_locations['mfc_chance'] = c_locations['mfc_chance'].apply(lambda x: 1 + 10* x / 42070.344117)
c_locations['mfc_score'] = c_locations['mfc_chance'].apply(lambda x: '⭐'*int(x))

#извлекаем ячейки выбранного в меню района Москвы
if print_all_btn:
    df = c_locations.copy()#.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]
else:
    df = c_locations.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]

#Выводим описание выьранного региона (население, площадь) и информацию 
st.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(df["customers_cnt_home"].values) + sum(df["customers_cnt_move"].values)} чел. на { df.shape[0]*0.25} км²
            Вы выбрали фильтрацию по учреждению типа: "{build_type}" с коэффициентом влияния равным {filter_value}
            с учётом того что это будет {filter_type.lower()}.
''')
#Собираем шаблон подсказки для столбцов(ячеек) карты
if filter_key != 'logistic':
    tooltip_template = "<b>" + filter_type + " :</b> {customers_cnt_"+filter_key+"} <br/><b>Необходисоть постройки "+build_type+" :</b> {mfc_score} <br/>"
else:
    tooltip_template = "<b>" + filter_type + " :</b> {logistic} <br/><b>Необходисоть постройки "+build_type+" :</b> {mfc_score} <br/>"

layers=[
        pdk.Layer("ColumnLayer", #слой для отображения колонок вероятности постройки учреждения
        data=df,
        get_position='[lon,lat]',
        get_elevation="mfc_chance",
        elevation_scale=100,
        radius=250,
        get_fill_color=["mfc_chance * 21","255-mfc_chance*21",1, 200],
        pickable=True,
        auto_highlight=True,
        ),
        pdk.Layer(
            "TextLayer",
            data=mfc_info_df,
            get_position='[lon,lat]',
            #get_text="mfc_chance",
            text='МФЦ',
            #elevation_scale=100,
            #radius=250,
            pickable=False,
            auto_highlight=True,
        )]

if show_mfc:
    layers.append(pdk.Layer("ColumnLayer", #слой для отображения уже существующих МФЦ
        data=mfc_info_df if print_all_btn else mfc_info_df.loc['район '+adm_zone.lower() == mfc_info_df['District'].str.lower() ],
        get_position='[lat,lon]',
        elevation=100,#"WindowCount",
        elevation_scale=1,
        radius=50,
        get_fill_color=[1,1,255, 200],
        pickable=True,
        auto_highlight=True,    
        ))




#Определяем графики на карте для районов и известных учреждений
world_map = pdk.Deck(
    map_style='mapbox://styles/mapbox/light-v9',
    initial_view_state=pdk.ViewState(latitude=df['lat'].values[0],longitude=df['lon'].values[0],zoom=11,pitch=50,),
     tooltip = {
        "html": tooltip_template,
        "style": {"backgroundColor": "black","color": "white"}
    },
    layers=layers,
)



success_box = None
def handle_on_click(widget_instance, payload):
    global success_box
    try:
        success_box.body = f'Вы выбрали ячейку {payload}!'
        coords = payload['data']['coordinate']
    except Exception as e:
        success_box.body = 'Error: %s' % e
world_map.deck_widget.on_click(handle_on_click)

map_widget = st.pydeck_chart(world_map)






#аналитика

col1, col2, col3 = st.columns(3)
col1.metric("Проживающие кол-во", str(sum(df['customers_cnt_home'].values)+sum(df['customers_cnt_move'].values)) + " чел.", str(sum(df['customers_dlt_home'].values)+sum(df['customers_dlt_move'].values)) + " чел.")
col2.metric("Работающие кол-во", str(sum(df['customers_cnt_job'].values)) + " чел.", str(sum(df['customers_dlt_job'].values)) + " чел.")
col3.metric("Дневное кол-во", str(sum(df['customers_cnt_day'].values)) + " чел.", str(sum(df['customers_dlt_day'].values)) + " чел.")



#st.write('Табличное представление загруженных данных')
#st.dataframe(c_locations)
#st.dataframe(loc_names)
#st.dataframe(s_df)
#st.dataframe(h_w_matrix)