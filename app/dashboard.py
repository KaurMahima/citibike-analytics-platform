import duckdb
import altair as alt
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import AntPath

DB_PATH = "../warehouse/citibike.duckdb"
MAP_CENTER = [40.73, -73.98]
MAP_TILES = "CartoDB positron"

st.set_page_config(page_title="Citi Bike Dashboard", layout="wide")


def run_query(query: str) -> pd.DataFrame:
    conn = duckdb.connect(DB_PATH)
    try:
        return conn.execute(query).fetchdf()
    finally:
        conn.close()


@st.cache_data
def load_daily_data() -> pd.DataFrame:
    df = run_query(
        """
        select *
        from fct_trip_daily_enriched
        order by trip_date
        """
    )
    df["trip_date"] = pd.to_datetime(df["trip_date"])
    return df


@st.cache_data
def load_station_daily_data() -> pd.DataFrame:
    df = run_query(
        """
        select *
        from fct_station_daily
        order by trip_date, trip_count desc
        """
    )
    df["trip_date"] = pd.to_datetime(df["trip_date"])
    return df


@st.cache_data
def load_station_hourly_data() -> pd.DataFrame:
    df = run_query(
        """
        select *
        from fct_station_hourly
        order by trip_date, trip_hour, trip_count desc
        """
    )
    df["trip_date"] = pd.to_datetime(df["trip_date"])
    return df


def build_date_list_sql(dates: list[pd.Timestamp]) -> str:
    return ", ".join(f"'{pd.Timestamp(date).date()}'" for date in dates)


@st.cache_data
def load_top_flows_daily(date_values: tuple[str, ...]) -> pd.DataFrame:
    if not date_values:
        return pd.DataFrame(
            columns=[
                "start_station_id",
                "start_station_name",
                "start_lat",
                "start_lng",
                "end_station_id",
                "end_station_name",
                "end_lat",
                "end_lng",
                "trip_count",
                "member_trips",
                "casual_trips",
            ]
        )

    date_sql = ", ".join(f"'{date_value}'" for date_value in date_values)
    return run_query(
        f"""
        select
            start_station_id,
            start_station_name,
            start_lat,
            start_lng,
            end_station_id,
            end_station_name,
            end_lat,
            end_lng,
            sum(trip_count) as trip_count,
            sum(member_trips) as member_trips,
            sum(casual_trips) as casual_trips
        from fct_station_flows_daily
        where trip_date in ({date_sql})
        group by
            start_station_id,
            start_station_name,
            start_lat,
            start_lng,
            end_station_id,
            end_station_name,
            end_lat,
            end_lng
        order by trip_count desc
        limit 100
        """
    )


@st.cache_data
def load_top_flows_hourly(
    date_values: tuple[str, ...],
    start_hour: int,
    end_hour: int,
    hour_buckets: tuple[str, ...],
    rush_filter: str,
) -> pd.DataFrame:
    if not date_values or not hour_buckets:
        return pd.DataFrame(
            columns=[
                "start_station_id",
                "start_station_name",
                "start_lat",
                "start_lng",
                "end_station_id",
                "end_station_name",
                "end_lat",
                "end_lng",
                "trip_count",
                "member_trips",
                "casual_trips",
            ]
        )

    date_sql = ", ".join(f"'{date_value}'" for date_value in date_values)
    bucket_sql = ", ".join(f"'{bucket}'" for bucket in hour_buckets)

    rush_clause = ""
    if rush_filter == "Rush hours only":
        rush_clause = "and is_rush_hour = true"
    elif rush_filter == "Non-rush hours only":
        rush_clause = "and is_rush_hour = false"

    return run_query(
        f"""
        select
            start_station_id,
            start_station_name,
            avg(start_lat) as start_lat,
            avg(start_lng) as start_lng,
            end_station_id,
            end_station_name,
            avg(end_lat) as end_lat,
            avg(end_lng) as end_lng,
            sum(trip_count) as trip_count,
            sum(member_trips) as member_trips,
            sum(casual_trips) as casual_trips
        from fct_station_flows_hourly
        where trip_date in ({date_sql})
          and trip_hour between {start_hour} and {end_hour}
          and hour_bucket in ({bucket_sql})
          {rush_clause}
        group by
            start_station_id,
            start_station_name,
            end_station_id,
            end_station_name
        order by trip_count desc
        limit 100
        """
    )


def render_station_map(map_df: pd.DataFrame, granularity_label: str) -> None:
    st.subheader("NYC Citi Bike Station Map")
    st.caption(f"Station activity for the selected filters at {granularity_label.lower()} granularity.")

    if map_df.empty:
        st.info("No station map data available for the selected filters.")
        return

    mapped = map_df.head(300).copy()

    nyc_map = folium.Map(
        location=MAP_CENTER,
        zoom_start=11,
        tiles=MAP_TILES,
        control_scale=True,
    )

    for _, row in mapped.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            color="#e74c3c",
            fill=True,
            fill_color="#e74c3c",
            fill_opacity=0.55,
            weight=0.5,
            popup=folium.Popup(
                f"""
                <b>{row['station_name']}</b><br>
                Trips: {int(row['trip_count']):,}<br>
                Member trips: {int(row['member_trips']):,}<br>
                Casual trips: {int(row['casual_trips']):,}
                """,
                max_width=250,
            ),
        ).add_to(nyc_map)

    st_folium(nyc_map, use_container_width=True, height=550)

    st.markdown("**Top mapped stations**")
    st.dataframe(
        mapped[["station_name", "trip_count", "member_trips", "casual_trips"]].head(15),
        use_container_width=True,
        hide_index=True,
    )


def render_flow_map(flow_df: pd.DataFrame, granularity_label: str) -> None:
    st.subheader("Top Citi Bike Flows")
    st.caption(f"Station-to-station movement for the selected filters at {granularity_label.lower()} granularity.")

    if flow_df.empty:
        st.info("No station flow data available for the selected filters.")
        return

    flow_map = folium.Map(
        location=MAP_CENTER,
        zoom_start=11,
        tiles=MAP_TILES,
        control_scale=True,
    )

    for _, row in flow_df.iterrows():
        AntPath(
            locations=[
                [row["start_lat"], row["start_lng"]],
                [row["end_lat"], row["end_lng"]],
            ],
            color="#2563eb",
            weight=max(2, min(8, row["trip_count"] / 20)),
            opacity=0.7,
            delay=800,
            dash_array=[12, 18],
            pulse_color="#60a5fa",
        ).add_to(flow_map)

        folium.Marker(
            location=[row["start_lat"], row["start_lng"]],
            popup=folium.Popup(
                f"""
                <b>{row['start_station_name']}</b> → <b>{row['end_station_name']}</b><br>
                Trips: {int(row['trip_count']):,}<br>
                Member trips: {int(row['member_trips']):,}<br>
                Casual trips: {int(row['casual_trips']):,}
                """,
                max_width=300,
            ),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(flow_map)

    st_folium(flow_map, use_container_width=True, height=550)

    st.markdown("**Top flow table**")
    flow_table = flow_df[
        [
            "start_station_name",
            "end_station_name",
            "trip_count",
            "member_trips",
            "casual_trips",
        ]
    ].rename(
        columns={
            "start_station_name": "origin_station",
            "end_station_name": "destination_station",
        }
    )
    st.dataframe(flow_table, use_container_width=True, hide_index=True)


daily_df = load_daily_data()
station_daily_df = load_station_daily_data()
station_hourly_df = load_station_hourly_data()

st.title("Citi Bike Dashboard")
st.caption("Daily Citi Bike trips enriched with weather, holiday, station, and hourly movement context.")

st.sidebar.header("Filters")

min_date = daily_df["trip_date"].min().date()
max_date = daily_df["trip_date"].max().date()

data_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

season_options = sorted(daily_df["season"].dropna().unique().tolist())
selected_seasons = st.sidebar.multiselect("Season", season_options, default=season_options)

holiday_filter = st.sidebar.selectbox(
    "Holiday filter",
    ["All", "Holidays only", "Non-holidays only"],
)

day_type_filter = st.sidebar.selectbox(
    "Day type",
    ["All", "Weekdays only", "Weekends only"],
)

day_name_options = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
selected_days = st.sidebar.multiselect(
    "Day of week",
    day_name_options,
    default=day_name_options,
)

year_options = sorted(daily_df["trip_date"].dt.year.unique().tolist())
selected_years = st.sidebar.multiselect("Year", year_options, default=year_options)

month_options = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
selected_months = st.sidebar.multiselect("Month", month_options, default=month_options)

st.sidebar.subheader("Mobility View")

granularity = st.sidebar.radio(
    "Granularity",
    ["Daily", "Hourly"],
    horizontal=False,
)

selected_hours = st.sidebar.slider(
    "Hour of day",
    min_value=0,
    max_value=23,
    value=(0, 23),
)

hour_bucket_options = [
    "Morning commute",
    "Midday",
    "Evening commute",
    "Night / Early morning",
]
selected_hour_buckets = st.sidebar.multiselect(
    "Hour bucket",
    hour_bucket_options,
    default=hour_bucket_options,
)

rush_hour_filter = st.sidebar.selectbox(
    "Rush hour filter",
    ["All", "Rush hours only", "Non-rush hours only"],
)

start_date, end_date = data_range

filtered_daily = daily_df[
    (daily_df["trip_date"] >= pd.to_datetime(start_date))
    & (daily_df["trip_date"] <= pd.to_datetime(end_date))
    & (daily_df["season"].isin(selected_seasons))
    & (daily_df["day_name"].isin(selected_days))
    & (daily_df["trip_date"].dt.year.isin(selected_years))
    & (daily_df["month_name"].isin(selected_months))
].copy()

if holiday_filter == "Holidays only":
    filtered_daily = filtered_daily[filtered_daily["is_holiday"] == True]
elif holiday_filter == "Non-holidays only":
    filtered_daily = filtered_daily[filtered_daily["is_holiday"] == False]

if day_type_filter == "Weekdays only":
    filtered_daily = filtered_daily[filtered_daily["is_weekend"] == False]
elif day_type_filter == "Weekends only":
    filtered_daily = filtered_daily[filtered_daily["is_weekend"] == True]

st.markdown(
    f"""
    **Current view:** {start_date} to {end_date} |
    **Seasons:** {", ".join(selected_seasons) if selected_seasons else "None"} |
    **Holiday:** {holiday_filter} |
    **Day type:** {day_type_filter} |
    **Granularity:** {granularity}
    """
)

if filtered_daily.empty:
    st.warning("No daily records match the selected filters.")
    st.stop()

valid_dates = sorted(filtered_daily["trip_date"].dt.strftime("%Y-%m-%d").unique().tolist())

total_trips = int(filtered_daily["total_trips"].sum())
avg_daily_trips = filtered_daily["total_trips"].mean()
avg_trip_duration = filtered_daily["avg_trip_duration_minutes"].mean()
member_share = (
    filtered_daily["member_trips"].sum()
    / (filtered_daily["member_trips"].sum() + filtered_daily["casual_trips"].sum())
    if (filtered_daily["member_trips"].sum() + filtered_daily["casual_trips"].sum()) > 0
    else 0
)

busiest_day_row = filtered_daily.loc[filtered_daily["total_trips"].idxmax()]
busiest_day = busiest_day_row["trip_date"].date()
busiest_day_trips = int(busiest_day_row["total_trips"])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Trips", f"{total_trips:,}")
col2.metric("Avg Daily Trips", f"{avg_daily_trips:.0f}")
col3.metric("Avg Trip Duration", f"{avg_trip_duration:.1f} min")
col4.metric("Member Share", f"{member_share:.1%}")
col5.metric("Busiest Day", f"{busiest_day}", f"{busiest_day_trips:,} trips")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Daily Trips Over Time")
    st.line_chart(filtered_daily.set_index("trip_date")["total_trips"])

with chart_col2:
    st.subheader("Member vs Casual Trips")
    member_casual = filtered_daily.set_index("trip_date")[["member_trips", "casual_trips"]]
    st.area_chart(member_casual)

bottom_col1, bottom_col2 = st.columns(2)

with bottom_col1:
    st.subheader("Average Trips by Day of Week")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = filtered_daily.groupby("day_name", as_index=False)["total_trips"].mean()
    by_day["day_name"] = pd.Categorical(by_day["day_name"], categories=day_order, ordered=True)
    by_day = by_day.sort_values("day_name")
    st.bar_chart(by_day.set_index("day_name")["total_trips"])

with bottom_col2:
    st.subheader("Trips vs Temperature")
    weather_df = filtered_daily[["trip_date", "total_trips", "temperature_max_c", "season"]].dropna()
    weather_chart = (
        alt.Chart(weather_df)
        .mark_circle(size=70, opacity=0.7)
        .encode(
            x=alt.X("temperature_max_c:Q", title="Max Temperature (C)"),
            y=alt.Y("total_trips:Q", title="Total Trips"),
            color=alt.Color("season:N", title="Season"),
            tooltip=[
                alt.Tooltip("trip_date:T", title="Date"),
                alt.Tooltip("total_trips:Q", title="Trips", format=","),
                alt.Tooltip("temperature_max_c:Q", title="Max Temp (C)", format=".1f"),
                alt.Tooltip("season:N", title="Season"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(weather_chart, use_container_width=True)

st.divider()
st.subheader("Mobility Explorer")

map_mode = st.radio(
    "Map view",
    ["Station activity", "Top flows"],
    horizontal=True,
)

if granularity == "Daily":
    station_filtered = station_daily_df[
        station_daily_df["trip_date"].dt.strftime("%Y-%m-%d").isin(valid_dates)
    ].copy()

    mobility_map_df = (
        station_filtered.groupby(
            ["station_id", "station_name", "lat", "lon"],
            as_index=False,
        )
        .agg(
            trip_count=("trip_count", "sum"),
            member_trips=("member_trips", "sum"),
            casual_trips=("casual_trips", "sum"),
        )
        .sort_values("trip_count", ascending=False)
    )

    flow_df = load_top_flows_daily(tuple(valid_dates))

else:
    station_filtered = station_hourly_df[
        station_hourly_df["trip_date"].dt.strftime("%Y-%m-%d").isin(valid_dates)
    ].copy()

    start_hour, end_hour = selected_hours
    station_filtered = station_filtered[
        (station_filtered["trip_hour"] >= start_hour)
        & (station_filtered["trip_hour"] <= end_hour)
    ]

    if selected_hour_buckets:
        station_filtered = station_filtered[
            station_filtered["hour_bucket"].isin(selected_hour_buckets)
        ]
    else:
        station_filtered = station_filtered.iloc[0:0]

    if rush_hour_filter == "Rush hours only":
        station_filtered = station_filtered[station_filtered["is_rush_hour"] == True]
    elif rush_hour_filter == "Non-rush hours only":
        station_filtered = station_filtered[station_filtered["is_rush_hour"] == False]

    hourly_chart_col1, hourly_chart_col2 = st.columns(2)

    with hourly_chart_col1:
        st.markdown("**Trips by Hour**")
        by_hour = (
            station_filtered.groupby("trip_hour", as_index=False)
            .agg(trip_count=("trip_count", "sum"))
            .sort_values("trip_hour")
        )

        hour_chart = (
            alt.Chart(by_hour)
            .mark_bar(color="#2563eb")
            .encode(
                x=alt.X("trip_hour:O", title="Hour of Day"),
                y=alt.Y("trip_count:Q", title="Trips"),
                tooltip=[
                    alt.Tooltip("trip_hour:O", title="Hour"),
                    alt.Tooltip("trip_count:Q", title="Trips", format=","),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(hour_chart, use_container_width=True)

    with hourly_chart_col2:
        st.markdown("**Member vs Casual by Hour**")
        by_hour_type = (
            station_filtered.groupby("trip_hour", as_index=False)
            .agg(
                member_trips=("member_trips", "sum"),
                casual_trips=("casual_trips", "sum"),
            )
            .sort_values("trip_hour")
        )

        hour_mix = by_hour_type.melt(
            id_vars="trip_hour",
            value_vars=["member_trips", "casual_trips"],
            var_name="rider_type",
            value_name="trip_count",
        )

        mix_chart = (
            alt.Chart(hour_mix)
            .mark_area(opacity=0.75)
            .encode(
                x=alt.X("trip_hour:O", title="Hour of Day"),
                y=alt.Y("trip_count:Q", title="Trips"),
                color=alt.Color(
                    "rider_type:N",
                    title="Rider Type",
                    scale=alt.Scale(
                        domain=["member_trips", "casual_trips"],
                        range=["#0f766e", "#f59e0b"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("trip_hour:O", title="Hour"),
                    alt.Tooltip("rider_type:N", title="Rider Type"),
                    alt.Tooltip("trip_count:Q", title="Trips", format=","),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(mix_chart, use_container_width=True)

    bucket_col1, bucket_col2 = st.columns(2)

    with bucket_col1:
        st.markdown("**Trips by Hour Bucket**")
        by_bucket = (
            station_filtered.groupby("hour_bucket", as_index=False)
            .agg(trip_count=("trip_count", "sum"))
            .sort_values("trip_count", ascending=False)
        )
        st.dataframe(by_bucket, use_container_width=True, hide_index=True)

    with bucket_col2:
        st.markdown("**Hourly Station Leaders**")
        top_hourly_stations = (
            station_filtered.groupby(["station_name"], as_index=False)
            .agg(
                trip_count=("trip_count", "sum"),
                member_trips=("member_trips", "sum"),
                casual_trips=("casual_trips", "sum"),
            )
            .sort_values("trip_count", ascending=False)
            .head(15)
        )
        st.dataframe(top_hourly_stations, use_container_width=True, hide_index=True)

    mobility_map_df = (
        station_filtered.groupby(
            ["station_id", "station_name", "lat", "lon"],
            as_index=False,
        )
        .agg(
            trip_count=("trip_count", "sum"),
            member_trips=("member_trips", "sum"),
            casual_trips=("casual_trips", "sum"),
        )
        .sort_values("trip_count", ascending=False)
    )

    flow_df = load_top_flows_hourly(
        tuple(valid_dates),
        start_hour,
        end_hour,
        tuple(selected_hour_buckets),
        rush_hour_filter,
    )

if map_mode == "Station activity":
    render_station_map(mobility_map_df, granularity)
else:
    render_flow_map(flow_df, granularity)

detail_col1, detail_col2 = st.columns(2)

with detail_col1:
    st.subheader("Top 10 Busiest Days")
    top_days = (
        filtered_daily[
            [
                "trip_date",
                "total_trips",
                "member_trips",
                "casual_trips",
                "avg_trip_duration_minutes",
                "holiday_name",
                "temperature_max_c",
            ]
        ]
        .sort_values("total_trips", ascending=False)
        .head(10)
        .rename(columns={"trip_date": "date"})
    )
    st.dataframe(top_days, use_container_width=True, hide_index=True)

with detail_col2:
    st.subheader("Filtered Data Export")
    export_df = filtered_daily.copy()
    export_df["trip_date"] = export_df["trip_date"].dt.date
    csv_data = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download filtered data as CSV",
        data=csv_data,
        file_name="citibike_dashboard_filtered.csv",
        mime="text/csv",
    )