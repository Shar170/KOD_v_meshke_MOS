import streamlit as st
import streamlit.components.v1 as components 
import pandas as pd
import pydeck as pdk
import shapefile
import random
import os
from config import config

ICON_URL = "https://cdn-icons-png.flaticon.com/512/1566/1566070.png"



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

def print_main_tooltip(small_dataset, full_dataset,adm_zone = '', print_all_btn = True , metrics_column = st):

    if adm_zone == '' :
        metrics_column.write("Москва")
    else:
        metrics_column.text(f"Район {adm_zone}",)
    if print_all_btn:
        small_dataset = full_dataset
        
        #colM.write(f'''Вы выбрали район "{adm_zone}" сейчас население в нём: {sum(small_dataset["customers_cnt_home"].values) + sum(small_dataset["customers_cnt_move"].values)} чел. на { small_dataset.shape[0]*0.25} км²''')
    metrics_column.metric("Проживающие кол-во\n человек", str(sum(small_dataset['customers_cnt_home'].values) + sum(small_dataset['customers_cnt_move'].values)), str(sum(small_dataset['customers_dlt_home'].values)+sum(small_dataset['customers_dlt_move'].values)))
    metrics_column.metric("Работающие кол-во\n человек", str(sum(small_dataset['customers_cnt_job'].values)) , str(sum(small_dataset['customers_dlt_job'].values)))
    metrics_column.metric("Дневное кол-во\n человек", str(sum(small_dataset['customers_cnt_day'].values)), str(sum(small_dataset['customers_dlt_day'].values)))

def show_map(small_dataset,mfc_df, hide_model = True, model_key = '', adm_zone = '', show_mfc = False, preview_lat = 55.752004,preview_lon = 37.617734, as_html = False, map_container = st, windows_count = 20):
    tooltip_template = '{metaInfo}'
    if model_key == 'mfc_chance_agreg':
        small_dataset['mfc_chance_agreg'] = small_dataset['mfc_chance_agreg'].apply(lambda x: 3.1415**(x))
        max_from_df = small_dataset['mfc_chance_agreg'].max()
        small_dataset['mfc_chance_agreg'] = 5 * small_dataset['mfc_chance_agreg'] / max_from_df

    if not hide_model and model_key != '': 
        layers=[
            pdk.Layer("ScatterplotLayer", #слой для отображения колонок вероятности постройки учреждения   Scatterplot
            data=small_dataset[['zid','lon', 'lat', 'metaInfo', model_key]],
            get_position='[lon,lat]',
            elevation = 1,# = "none",#=model_key,
            elevation_scale=0,
            get_radius=250,
            #get_hex = 'zid',
            get_fill_color=[ f"{model_key} * 42 - 15",f"255-{model_key}*42",10,f"100+{model_key}*22"],# f"{model_key} * 42 - 15"],
            #get_border_color=[f"{model_key} * 42 - 15",f"255-{model_key}*42",20, 100],
            pickable=True,
            auto_highlight=True,
            )]
    elif hide_model or model_key == '':
        adm_df = load_shp("admzones2021.shp", "admzones2021.dbf")
        adm_df.dropna(inplace=True)

        layers=[pdk.Layer("TripsLayer", 
            data=adm_df.loc[adm_df['adm_name'] == adm_zone] if adm_zone != '' else adm_df,
            get_path='coords',
            get_color=[253, 128, 93],
            width_min_pixels=5,
            )]
    icon_data = {
        "url": ICON_URL,
        "width": 300,
        "height": 300,
        "anchorY": 300,
    }
    mfc_df["icon_data"] = None
    mfc_df['icon_data'] =  mfc_df['icon_data'].apply(lambda x: icon_data)
    mfc_df['size'] =  mfc_df['icon_data'].apply(lambda x: 10)

    if show_mfc:
        layers.append(pdk.Layer(type="IconLayer", #слой для отображения уже существующих МФЦ
            data=mfc_df, 
            get_icon="icon_data",
            get_size='size',
            size_scale=5,
            get_position=["lat", "lon"],
            pickable=True,
            ))

        # layers.append(pdk.Layer("ColumnLayer", #слой для отображения уже существующих МФЦ
        #     data=mfc_df[['lon', 'lat', 'metaInfo']],
        #     get_position='[lat,lon]',
        #     elevation=100,#"WindowCount",
        #     elevation_scale=1,
        #     radius=50,
        #     get_fill_color=[1,1,255, 200],
        #     pickable=True,
        #     auto_highlight=True,    
        #     ))

    #Инициализируем карту районов и известных учреждений

    world_map = pdk.Deck(
        map_style=pdk.map_styles.ROAD,#'mapbox://styles/mapbox/light-v9',
        api_keys = {'mapbox':'pk.eyJ1Ijoic2hhcjE3MCIsImEiOiJja3ZrMHg3anowcnEwMm50azdleG1teGVsIn0.QiZrdcW2axiKO4zN3M-lGg'},
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

    mapboxglMap.ondblclick = async e => {
        if (deckInstance._lastPointerDownInfo != null ) {
            coords = await deckInstance._lastPointerDownInfo.object;
            console.log(coords.lat, coords.lon);
            window.open(`http://"""+config['host']+""":8501/?tab=Строительство&target_zid=${coords.zid}&windows_count="""+ str(windows_count) + """`);
        }
    }
    """
    #let res = await axios.get(`http://localhost:8501/?tab=Строительство&target_zid=${coords.zid}`)

    library_code = '<script src="https://cdnjs.cloudflare.com/ajax/libs/axios/0.24.0/axios.min.js" integrity="sha512-u9akINsQsAkG9xjc1cnGF4zw5TFDwkxuc9vUp5dltDWYCSmyd0meygbvgXrlc/z7/o4a19Fb5V0OUE58J7dcyw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>'

    map_legend = '🔴 - Высокая потребность в учреждении  🟡 - Средняя потребность в учреждении    🟢 - Низкая потребность в учреждении'

    if as_html: #active_tab == tabs[1]:
        random_file = f'{random.randint(10000,1000000)}_map.html'
        world_map.to_html(random_file)
        html_code = open(random_file).readlines()
        html_code.insert(62,click_code)
        html_code.insert(9,library_code)
        os.remove(random_file)
        #st.markdown(' '.join(html_code), unsafe_allow_html=True)
        with map_container:
            components.html(' '.join(html_code), height=600)
            st.write(map_legend)
    else:
        map_container.pydeck_chart(world_map)
        map_container.write(map_legend)



