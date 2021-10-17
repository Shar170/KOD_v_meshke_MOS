import pandas as pd
import numpy as np
import pydeck as pdk
import shapefile
import streamlit as st

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
    #loc_names = pd.read_excel('names.xlsx')
    #loc_names['cell_zid'] = loc_names['cell_zid'].map(int)
    #loc_names['adm_zid'] = loc_names['adm_zid'].map(int)
    #loc_names.to_csv('rebuilded_names.csv')
    loc_names = pd.read_csv('rebuilded_names.csv')
    return loc_names.merge(right=s_df, how='inner', left_on='cell_zid', right_on='cell_zid')

@st.cache
def load_loc_info():
    #считываем информацию о плотности проживающего, работающего и проходящего населения для каждого квадрата и прикручиваем туда координаты квадратов
    c_locations = pd.read_csv("june_full_data.csv")
    # c_locations = c_locations.merge(right=s_df, how='inner', left_on='zid', right_on='cell_zid')
    # c_locations.drop('cell_zid', axis=1, inplace=True)
    # c_locations['lat'] = c_locations['coords'].apply(lambda x: x[0][1]) # извлекаем широту
    # c_locations['lon'] = c_locations['coords'].apply(lambda x: x[0][0]) # извлекаем долготу
    # c_locations.drop('coords', axis=1, inplace=True)
    return c_locations
@st.cache
def get_unic_names():
    return  pd.read_csv('rebuilded_names.csv')['adm_name'].drop_duplicates(inplace=False).values

loc_names = load_names()# pd.DataFrame.copy() #.copy(deep=True)
c_locations = load_loc_info()
h_w_matrix = load_h_w()
adm_names = get_unic_names()#loc_names['adm_name'].drop_duplicates(inplace=False).values

st.title('Проект команды "KOD в мешке"')
st.write('Карта Москвы и МО. Красные круги отображают выбранный вами район')
b_types_array = ['Больница','Школа','Магазин']

adm_zone = st.sidebar.selectbox('Выберите административную зону',adm_names, )
build_type = st.sidebar.selectbox('Выберите тип учреждения',b_types_array)
filter_type = st.sidebar.selectbox('Выберите фильтр',['Кол-во живущих','Кол-во работающих','Кол-во проходящях'])
filter_value = st.sidebar.slider('Выберите промежуток', value=(0,1), min_value=0, max_value=1000)
#press_button = st.sidebar.button("Do magic!")


df = c_locations.loc[c_locations['zid'].isin(loc_names.loc[loc_names['adm_name'] == adm_zone]['cell_zid'])]

st.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(df["customers_cnt_home"].values)}чел. на { df.shape[0]*0.25} км²
            Вы выбрали фильтрацию по учреждению типа: "{build_type}" с ожидаемым потоком людей в пределах между {filter_value}
            с учётом того что это будет {filter_type.lower()}.
''')


st.pydeck_chart(pdk.Deck(
    map_style='mapbox://styles/mapbox/light-v9',
    initial_view_state=pdk.ViewState(latitude=df['lat'].values[0],longitude=df['lon'].values[0],zoom=11,pitch=50,),
    layers=[
        pdk.Layer("ColumnLayer",
    data=df,
    
    get_position='[lon,lat]',
    get_elevation="mfc_chance",
    elevation_scale=100,#max(c_locations['customers_cnt_home'].values)/max(df['customers_cnt_home'].values),
    radius=250,
    get_fill_color=["255-mfc_chance * 21","mfc_chance*21",1, 200],
    pickable=True,
    auto_highlight=True,
    
    )
        #pdk.Layer('ScatterplotLayer',data=df,get_position='[lon,lat]',get_color='[200, 30, 0, 160]',get_radius=250,)
        #pdk.Layer("ScreenGridLayer",df,pickable=False,opacity=0.8,cell_size_pixels=5,color_range=[[0, 25, 0, 25],[0, 85, 0, 85],[0, 127, 0, 127],[0, 170, 0, 170],[0, 190, 0, 190],[0, 255, 0, 255],],get_position='[lon,lat]',get_weight=10,)
    ],
))








#st.write('Табличное представление загруженных данных')
#st.dataframe(c_locations)
#st.dataframe(loc_names)
#st.dataframe(s_df)
#st.dataframe(h_w_matrix)