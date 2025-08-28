import streamlit as st
import pandas as pd
import snowflake.connector
import plotly.graph_objects as go
import plotly.express as px
import plotly.graph_objects as go
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# --- Page Config ------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Squid Router Dashboard",
    page_icon="https://img.cryptorank.io/coins/squid1675241862798.png",
    layout="wide"
)

# --- Title with Logo -----------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px;">
        <img src="https://img.cryptorank.io/coins/squid1675241862798.png" alt="Squid Logo" style="width:60px; height:60px;">
        <h1 style="margin: 0;">Squid Router Dashboard</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Builder Info ---------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 20px; margin-bottom: 20px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/1841479747332608000/bindDGZQ_400x400.jpg" style="width:25px; height:25px; border-radius: 50%;">
            <span>Built by: <a href="https://x.com/0xeman_raz" target="_blank">Eman Raz</a></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.info("📊Charts initially display data for a default time range. Select a custom range to view results for your desired period.")
st.info("⏳On-chain data retrieval may take a few moments. Please wait while the results load.")

# --- Snowflake Connection ----------------------------------------------------------------------------------------
snowflake_secrets = st.secrets["snowflake"]
user = snowflake_secrets["user"]
account = snowflake_secrets["account"]
private_key_str = snowflake_secrets["private_key"]
warehouse = snowflake_secrets.get("warehouse", "")
database = snowflake_secrets.get("database", "")
schema = snowflake_secrets.get("schema", "")

private_key_pem = f"-----BEGIN PRIVATE KEY-----\n{private_key_str}\n-----END PRIVATE KEY-----".encode("utf-8")
private_key = serialization.load_pem_private_key(
    private_key_pem,
    password=None,
    backend=default_backend()
)
private_key_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

conn = snowflake.connector.connect(
    user=user,
    account=account,
    private_key=private_key_bytes,
    warehouse=warehouse,
    database=database,
    schema=schema
)

# --- Date Inputs ---------------------------------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    timeframe = st.selectbox("Select Time Frame", ["month", "week", "day"])

with col2:
    start_date = st.date_input("Start Date", value=pd.to_datetime("2024-01-01"))

with col3:
    end_date = st.date_input("End Date", value=pd.to_datetime("2025-08-31"))
# --- Query Function: Row1 --------------------------------------------------------------------------------------
@st.cache_data
def load_kpi_data(timeframe, start_date, end_date):
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
        -- Token Transfers
        SELECT 
            created_at, 
            LOWER(data:send:original_source_chain) AS source_chain, 
            LOWER(data:send:original_destination_chain) AS destination_chain,
            recipient_address AS user, 
            CASE 
              WHEN IS_ARRAY(data:send:amount) THEN NULL
              WHEN IS_OBJECT(data:send:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
              WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
              ELSE NULL
            END AS amount_usd,
            CASE 
              WHEN IS_ARRAY(data:send:fee_value) THEN NULL
              WHEN IS_OBJECT(data:send:fee_value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:fee_value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:fee_value::STRING)
              ELSE NULL
            END AS fee,
            id, 
            'Token Transfers' AS Service, 
            data:link:asset::STRING AS raw_asset
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND (
            sender_address ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR sender_address ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR sender_address ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR sender_address ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR sender_address ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )

        UNION ALL

        -- GMP
        SELECT  
            created_at,
            data:call.chain::STRING AS source_chain,
            data:call.returnValues.destinationChain::STRING AS destination_chain,
            data:call.transaction.from::STRING AS user,
            CASE 
              WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
              ELSE NULL
            END AS amount_usd,
            COALESCE(
              CASE 
                WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
                  OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
                THEN NULL
                WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
                  AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
                ELSE NULL
              END,
              CASE 
                WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
                WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
                ELSE NULL
              END
            ) AS fee,
            id, 
            'GMP' AS Service, 
            data:symbol::STRING AS raw_asset
        FROM axelar.axelscan.fact_gmp 
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND (
            data:approved:returnValues:contractAddress ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR data:approved:returnValues:contractAddress ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR data:approved:returnValues:contractAddress ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR data:approved:returnValues:contractAddress ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR data:approved:returnValues:contractAddress ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
    )
    SELECT 
        COUNT(DISTINCT id) AS Number_of_Transfers, 
        COUNT(DISTINCT user) AS Number_of_Users, 
        ROUND(SUM(amount_usd)) AS Volume_of_Transfers,
        ROUND(median(amount_usd)) AS Median_Bridged_Volume,
        ROUND(max(amount_usd)) AS Maximum_Bridged_Volume,
        ROUND(avg(amount_usd)) AS Average_Bridged_Volume
        
    FROM axelar_service
    WHERE created_at::date >= '{start_str}' 
      AND created_at::date <= '{end_str}'
    """

    df = pd.read_sql(query, conn)
    return df

# --- Load Data ----------------------------------------------------------------------------------------------------
df_kpi = load_kpi_data(timeframe, start_date, end_date)

# --- KPI Row (1) ------------------------------------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric(
    label="Bridged Volume",
    value=f"${df_kpi['VOLUME_OF_TRANSFERS'][0]:,}"
)

col2.metric(
    label="Total Bridges",
    value=f"{df_kpi['NUMBER_OF_TRANSFERS'][0]:,} Txns"
)

col3.metric(
    label="Total Bridgers",
    value=f"{df_kpi['NUMBER_OF_USERS'][0]:,} Addresses"
)


# --- KPI Row (2) ------------------------------------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric(
    label="Median Bridged Volume",
    value=f"${df_kpi['MEDIAN_BRIDGED_VOLUME'][0]:,}"
)

col2.metric(
    label="Maximum Bridged Volume",
    value=f"${df_kpi['MAXIMUM_BRIDGED_VOLUME'][0]:,}"
)

col3.metric(
    label="Average Bridged Volume",
    value=f"${df_kpi['AVERAGE_BRIDGED_VOLUME'][0]:,}"
)

# --- Query Function: Row (3) --------------------------------------------------------------------------------------
@st.cache_data
def load_time_series_data(timeframe, start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
        -- Token Transfers
        SELECT 
            created_at, 
            LOWER(data:send:original_source_chain) AS source_chain, 
            LOWER(data:send:original_destination_chain) AS destination_chain,
            recipient_address AS user, 
            CASE 
              WHEN IS_ARRAY(data:send:amount) THEN NULL
              WHEN IS_OBJECT(data:send:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
              WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
              ELSE NULL
            END AS amount_usd,
            CASE 
              WHEN IS_ARRAY(data:send:fee_value) THEN NULL
              WHEN IS_OBJECT(data:send:fee_value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:fee_value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:fee_value::STRING)
              ELSE NULL
            END AS fee,
            id, 
            'Token Transfers' AS Service, 
            data:link:asset::STRING AS raw_asset
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND (
            sender_address ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR sender_address ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR sender_address ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR sender_address ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR sender_address ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )

        UNION ALL

        -- GMP
        SELECT  
            created_at,
            data:call.chain::STRING AS source_chain,
            data:call.returnValues.destinationChain::STRING AS destination_chain,
            data:call.transaction.from::STRING AS user,
            CASE 
              WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
              ELSE NULL
            END AS amount_usd,
            COALESCE(
              CASE 
                WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
                  OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
                THEN NULL
                WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
                  AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
                ELSE NULL
              END,
              CASE 
                WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
                WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
                ELSE NULL
              END
            ) AS fee,
            id, 
            'GMP' AS Service, 
            data:symbol::STRING AS raw_asset
        FROM axelar.axelscan.fact_gmp 
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND (
            data:approved:returnValues:contractAddress ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR data:approved:returnValues:contractAddress ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR data:approved:returnValues:contractAddress ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR data:approved:returnValues:contractAddress ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR data:approved:returnValues:contractAddress ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
    )
    SELECT 
        DATE_TRUNC('{timeframe}', created_at) AS Date,
        COUNT(DISTINCT id) AS Number_of_Bridges, 
        COUNT(DISTINCT user) AS Number_of_Bridgers, 
        ROUND(SUM(amount_usd)) AS Bridged_Volume,
        SUM(Bridged_Volume) OVER (ORDER BY Date) AS Total_Bridged_Volume,
        SUM(Number_of_Bridges) OVER (ORDER BY Date) AS Total_Number_of_Bridges,
        round((COUNT(DISTINCT id)/COUNT(DISTINCT user)),1) as Avg_Bridge_Count_per_User,
        avg(amount_usd) as Avg_Bridged_Volume
    FROM axelar_service
    WHERE created_at::date >= '{start_str}' 
      AND created_at::date <= '{end_str}'
    GROUP BY 1
    ORDER BY 1
    """

    return pd.read_sql(query, conn)

# --- Load Data ----------------------------------------------------------------------------------------------------
df_ts = load_time_series_data(timeframe, start_date, end_date)

col1, col2 = st.columns(2)

with col1:
    fig1 = go.Figure()
    fig1.add_bar(x=df_ts["DATE"], y=df_ts["NUMBER_OF_BRIDGES"], name="Number of Bridges", yaxis="y1")
    fig1.add_trace(go.Scatter(x=df_ts["DATE"], y=df_ts["TOTAL_NUMBER_OF_BRIDGES"], name="Total Number of Bridges", mode="lines+markers", yaxis="y2"))
    fig1.update_layout(
        title="Number of Bridges Over Time",
        yaxis=dict(title="Txns count"),
        yaxis2=dict(title="Txns count", overlaying="y", side="right"),
        xaxis=dict(title=" "),
        barmode="group",
        legend=dict(
        orientation="h",   
        yanchor="bottom", 
        y=1.05,           
        xanchor="center",  
        x=0.5
    )
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig2 = go.Figure()
    fig2.add_bar(x=df_ts["DATE"], y=df_ts["BRIDGED_VOLUME"], name="Bridged Volume", yaxis="y1")
    fig2.add_trace(go.Scatter(x=df_ts["DATE"], y=df_ts["TOTAL_BRIDGED_VOLUME"], name="Total Bridged Volume", mode="lines+markers", yaxis="y2"))
    fig2.update_layout(
        title="Bridged Volume Over Time",
        yaxis=dict(title="$USD"),
        yaxis2=dict(title="$USD", overlaying="y", side="right"),
        xaxis=dict(title=" "),
        barmode="group",
        legend=dict(
        orientation="h",   
        yanchor="bottom", 
        y=1.05,           
        xanchor="center",  
        x=0.5
    )
    )
    st.plotly_chart(fig2, use_container_width=True)


col1, col2 = st.columns(2)

with col1:
    fig1 = go.Figure()
    fig1.add_bar(x=df_ts["DATE"], y=df_ts["NUMBER_OF_BRIDGERS"], name="Number of Bridgers", yaxis="y1")
    fig1.add_trace(go.Scatter(x=df_ts["DATE"], y=df_ts["AVG_BRIDGE_COUNT_PER_USER"], name="Avg Bridge Count per User", mode="lines+markers", yaxis="y2"))
    fig1.update_layout(
        title="Number of Bridgers Over Time",
        yaxis=dict(title="User count"),
        yaxis2=dict(title="Txns count", overlaying="y", side="right"),
        xaxis=dict(title=" "),
        barmode="group",
        legend=dict(
        orientation="h",   
        yanchor="bottom", 
        y=1.05,           
        xanchor="center",  
        x=0.5
    )
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=df_ts["DATE"],
            y=df_ts["AVG_BRIDGED_VOLUME"],
            name="Avg Bridged Volume",
            mode="lines+markers"
        )
    )
    fig2.update_layout(
        title="Avg Bridged Volume per Transaction Over Time",
        yaxis=dict(title="$USD"),
        xaxis=dict(title=" ")
    )
    st.plotly_chart(fig2, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------------
# --- Query Function: Row (3) ------------------------------------------------------------------------------------------------
@st.cache_data
def load_source_chain_data(start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
        -- Token Transfers
        SELECT 
            created_at, 
            LOWER(data:send:original_source_chain) AS source_chain, 
            LOWER(data:send:original_destination_chain) AS destination_chain,
            recipient_address AS user, 
            CASE 
              WHEN IS_ARRAY(data:send:amount) THEN NULL
              WHEN IS_OBJECT(data:send:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
              WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
              ELSE NULL
            END AS amount_usd,
            CASE 
              WHEN IS_ARRAY(data:send:fee_value) THEN NULL
              WHEN IS_OBJECT(data:send:fee_value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:send:fee_value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:fee_value::STRING)
              ELSE NULL
            END AS fee,
            id, 
            'Token Transfers' AS Service, 
            data:link:asset::STRING AS raw_asset
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND created_at::date >= '{start_str}' 
          AND created_at::date <= '{end_str}'
          AND (
            sender_address ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR sender_address ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR sender_address ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR sender_address ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR sender_address ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )

        UNION ALL

        -- GMP
        SELECT  
            created_at,
            data:call.chain::STRING AS source_chain,
            data:call.returnValues.destinationChain::STRING AS destination_chain,
            data:call.transaction.from::STRING AS user,
            CASE 
              WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
              WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
              ELSE NULL
            END AS amount,
            CASE 
              WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
              WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
              ELSE NULL
            END AS amount_usd,
            COALESCE(
              CASE 
                WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
                  OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
                THEN NULL
                WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
                  AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
                THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
                ELSE NULL
              END,
              CASE 
                WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
                WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
                ELSE NULL
              END
            ) AS fee,
            id, 
            'GMP' AS Service, 
            data:symbol::STRING AS raw_asset
        FROM axelar.axelscan.fact_gmp 
        WHERE status = 'executed'
          AND simplified_status = 'received'
          AND created_at::date >= '{start_str}' 
          AND created_at::date <= '{end_str}'
          AND (
            data:approved:returnValues:contractAddress ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' 
            OR data:approved:returnValues:contractAddress ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
            OR data:approved:returnValues:contractAddress ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
            OR data:approved:returnValues:contractAddress ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
            OR data:approved:returnValues:contractAddress ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
    )
    SELECT source_chain AS "Source Chain", 
           COUNT(DISTINCT id) AS "Number of Transfers", 
           COUNT(DISTINCT user) AS "Number of Users", 
           ROUND(SUM(amount_usd)) AS "Volume of Transfers (USD)"
    FROM axelar_service
    GROUP BY 1
    ORDER BY 2 DESC
    """

    return pd.read_sql(query, conn)

# --- Load Data ----------------------------------------------------------------------------------------------------
df_source = load_source_chain_data(start_date, end_date)

# --- Display Table ------------------------------------------------------------------------------------------------
st.subheader("📤Squid Activity by Source Chain")

df_display = df_source.copy()
df_display.index = df_display.index + 1
df_display = df_display.applymap(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
st.dataframe(df_display, use_container_width=True)

# --- Top 10 Horizontal Bar Charts ----------------------------------------------------------------------------------
top_vol = df_source.nlargest(10, "Volume of Transfers (USD)")
top_txn = df_source.nlargest(10, "Number of Transfers")
top_usr = df_source.nlargest(10, "Number of Users")

col1, col2, col3 = st.columns(3)

with col1:
    fig1 = px.bar(
        top_vol.sort_values("Volume of Transfers (USD)"),
        x="Volume of Transfers (USD)", y="Source Chain",
        orientation="h",
        title="Top 10 Source Chains by Volume (USD)",
        labels={"Volume of Transfers (USD)": "USD", "Source Chain": " "},
        color_discrete_sequence=["#ca99e5"]
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig2 = px.bar(
        top_txn.sort_values("Number of Transfers"),
        x="Number of Transfers", y="Source Chain",
        orientation="h",
        title="Top 10 Source Chains by Transfers",
        labels={"Number of Transfers": "Txns count", "Source Chain": " "},
        color_discrete_sequence=["#ca99e5"]
    )
    st.plotly_chart(fig2, use_container_width=True)

with col3:
    fig3 = px.bar(
        top_usr.sort_values("Number of Users"),
        x="Number of Users", y="Source Chain",
        orientation="h",
        title="Top 10 Source Chains by Users",
        labels={"Number of Users": "Address count", "Source Chain": " "},
        color_discrete_sequence=["#ca99e5"]
    )
    st.plotly_chart(fig3, use_container_width=True)

# --- Destination Chain Data Query: Row 5, 6 --------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_destination_data(start_date, end_date):
    # ensure string format YYYY-MM-DD
    start_str = pd.to_datetime(start_date).strftime("%Y-%m-%d")
    end_str = pd.to_datetime(end_date).strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
      SELECT 
        created_at, 
        LOWER(data:send:original_source_chain) AS source_chain, 
        LOWER(data:send:original_destination_chain) AS destination_chain,
        recipient_address AS user, 
        CASE 
          WHEN IS_ARRAY(data:send:amount) THEN NULL
          WHEN IS_OBJECT(data:send:amount) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING)
          ELSE NULL
        END AS amount,
        CASE 
          WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
          WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
            THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
          ELSE NULL
        END AS amount_usd,
        CASE 
          WHEN IS_ARRAY(data:send:fee_value) THEN NULL
          WHEN IS_OBJECT(data:send:fee_value) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:fee_value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:fee_value::STRING)
          ELSE NULL
        END AS fee,
        id, 
        'Token Transfers' AS "Service", 
        data:link:asset::STRING AS raw_asset
      FROM axelar.axelscan.fact_transfers
      WHERE status = 'executed'
        AND simplified_status = 'received'
        AND created_at::date >= '{start_str}'
        AND created_at::date <= '{end_str}'
        AND (
          sender_address ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          OR sender_address ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          OR sender_address ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          OR sender_address ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          OR sender_address ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
        )

      UNION ALL

      SELECT  
        created_at,
        data:call.chain::STRING AS source_chain,
        data:call.returnValues.destinationChain::STRING AS destination_chain,
        data:call.transaction.from::STRING AS user,
        CASE 
          WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
          WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
          ELSE NULL
        END AS amount,
        CASE 
          WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
          WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
          ELSE NULL
        END AS amount_usd,
        COALESCE(
          CASE 
            WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
              OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
            THEN NULL
            WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
              AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
            THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
            ELSE NULL
          END,
          CASE 
            WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
            WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
            ELSE NULL
          END
        ) AS fee,
        id, 
        'GMP' AS "Service", 
        data:symbol::STRING AS raw_asset
      FROM axelar.axelscan.fact_gmp 
      WHERE status = 'executed'
        AND simplified_status = 'received'
        AND created_at::date >= '{start_str}'
        AND created_at::date <= '{end_str}'
        AND (
          data:approved:returnValues:contractAddress ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          OR data:approved:returnValues:contractAddress ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
        )
    )

    SELECT 
      destination_chain AS "Destination Chain", 
      COUNT(DISTINCT id) AS "Number of Transfers", 
      COUNT(DISTINCT user) AS "Number of Users", 
      ROUND(SUM(amount_usd)) AS "Volume of Transfers (USD)"
    FROM axelar_service
    GROUP BY 1
    ORDER BY "Number of Transfers" DESC
    """

    df = pd.read_sql(query, conn)

    # normalize column names for easier downstream use
    df = df.rename(columns={
        "Destination Chain": "Destination Chain",
        "Number of Transfers": "Number of Transfers",
        "Number of Users": "Number of Users",
        "Volume of Transfers (USD)": "Volume of Transfers (USD)"
    })

    return df

# --- Use the cached loader ---------------------------------------------------------
df_dest = load_destination_data(start_date, end_date)

# --- show table -----------------------------------------------------------------
st.subheader("📥Squid Activity by Destination Chain")
df_display = df_dest.copy()
df_display.index = df_display.index + 1
df_display = df_display.applymap(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
st.dataframe(df_display, use_container_width=True)

# --- prepare top-10s and charts (horizontal bars) ------------------------------------
top_vol_dest = df_dest.nlargest(10, "Volume of Transfers (USD)").sort_values("Volume of Transfers (USD)", ascending=False)
top_txn_dest = df_dest.nlargest(10, "Number of Transfers").sort_values("Number of Transfers", ascending=False)
top_usr_dest = df_dest.nlargest(10, "Number of Users").sort_values("Number of Users", ascending=False)

fig_vol_dest = px.bar(
    top_vol_dest,
    x="Volume of Transfers (USD)",
    y="Destination Chain",
    orientation="h",
    title="Top 10 Destination Chains by Volume (USD)",
    labels={"Volume of Transfers (USD)": "USD", "Destination Chain": " "},
    color_discrete_sequence=["#ca99e5"]
)
fig_vol_dest.update_xaxes(tickformat=",.0f")
fig_vol_dest.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
fig_vol_dest.update_yaxes(autorange="reversed")  

fig_txn_dest = px.bar(
    top_txn_dest,
    x="Number of Transfers",
    y="Destination Chain",
    orientation="h",
    title="Top 10 Destination Chains by Transfers",
    labels={"Number of Transfers": "Txns count", "Destination Chain": " "},
    color_discrete_sequence=["#ca99e5"]
)
fig_txn_dest.update_xaxes(tickformat=",.0f")
fig_txn_dest.update_traces(hovertemplate="%{y}: %{x:,}<extra></extra>")
fig_txn_dest.update_yaxes(autorange="reversed")

fig_usr_dest = px.bar(
    top_usr_dest,
    x="Number of Users",
    y="Destination Chain",
    orientation="h",
    title="Top 10 Destination Chains by Users",
    labels={"Number of Users": "Addresses count", "Destination Chain": " "},
    color_discrete_sequence=["#ca99e5"]
)
fig_usr_dest.update_xaxes(tickformat=",.0f")
fig_usr_dest.update_traces(hovertemplate="%{y}: %{x:,}<extra></extra>")
fig_usr_dest.update_yaxes(autorange="reversed")

# --- display three charts in one row -----------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.plotly_chart(fig_vol_dest, use_container_width=True)
with col2:
    st.plotly_chart(fig_txn_dest, use_container_width=True)
with col3:
    st.plotly_chart(fig_usr_dest, use_container_width=True)

# --- Cached loader for Path metrics: Row 7, 8 ----------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_path_data(start_date, end_date):
    start_str = pd.to_datetime(start_date).strftime("%Y-%m-%d")
    end_str = pd.to_datetime(end_date).strftime("%Y-%m-%d")

    query = f"""
    WITH axelar_service AS (
      SELECT 
        created_at, 
        LOWER(data:send:original_source_chain) AS source_chain, 
        LOWER(data:send:original_destination_chain) AS destination_chain,
        recipient_address AS user, 
        CASE 
          WHEN IS_ARRAY(data:send:amount) THEN NULL
          WHEN IS_OBJECT(data:send:amount) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:amount::STRING)
          ELSE NULL
        END AS amount,
        CASE 
          WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
          WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
            THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
          ELSE NULL
        END AS amount_usd,
        CASE 
          WHEN IS_ARRAY(data:send:fee_value) THEN NULL
          WHEN IS_OBJECT(data:send:fee_value) THEN NULL
          WHEN TRY_TO_DOUBLE(data:send:fee_value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:send:fee_value::STRING)
          ELSE NULL
        END AS fee,
        id, 
        'Token Transfers' AS "Service", 
        data:link:asset::STRING AS raw_asset
      FROM axelar.axelscan.fact_transfers
      WHERE status = 'executed'
        AND simplified_status = 'received'
        AND created_at::date >= '{start_str}'
        AND created_at::date <= '{end_str}'
        AND (
          sender_address ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          OR sender_address ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          OR sender_address ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          OR sender_address ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          OR sender_address ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
        )
      UNION ALL
      SELECT  
        created_at,
        data:call.chain::STRING AS source_chain,
        data:call.returnValues.destinationChain::STRING AS destination_chain,
        data:call.transaction.from::STRING AS user,
        CASE 
          WHEN IS_ARRAY(data:amount) OR IS_OBJECT(data:amount) THEN NULL
          WHEN TRY_TO_DOUBLE(data:amount::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:amount::STRING)
          ELSE NULL
        END AS amount,
        CASE 
          WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
          WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
          ELSE NULL
        END AS amount_usd,
        COALESCE(
          CASE 
            WHEN IS_ARRAY(data:gas:gas_used_amount) OR IS_OBJECT(data:gas:gas_used_amount) 
              OR IS_ARRAY(data:gas_price_rate:source_token.token_price.usd) OR IS_OBJECT(data:gas_price_rate:source_token.token_price.usd) 
            THEN NULL
            WHEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) IS NOT NULL 
              AND TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING) IS NOT NULL 
            THEN TRY_TO_DOUBLE(data:gas:gas_used_amount::STRING) * TRY_TO_DOUBLE(data:gas_price_rate:source_token.token_price.usd::STRING)
            ELSE NULL
          END,
          CASE 
            WHEN IS_ARRAY(data:fees:express_fee_usd) OR IS_OBJECT(data:fees:express_fee_usd) THEN NULL
            WHEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:fees:express_fee_usd::STRING)
            ELSE NULL
          END
        ) AS fee,
        id, 
        'GMP' AS "Service", 
        data:symbol::STRING AS raw_asset
      FROM axelar.axelscan.fact_gmp 
      WHERE status = 'executed'
        AND simplified_status = 'received'
        AND created_at::date >= '{start_str}'
        AND created_at::date <= '{end_str}'
        AND (
          data:approved:returnValues:contractAddress ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          OR data:approved:returnValues:contractAddress ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          OR data:approved:returnValues:contractAddress ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
        )
    )
    SELECT 
      source_chain || '➡' || destination_chain AS path, 
      COUNT(DISTINCT id) AS "Number of Transfers", 
      COUNT(DISTINCT user) AS "Number of Users", 
      ROUND(SUM(amount_usd)) AS "Volume of Transfers USD"
    FROM axelar_service
    GROUP BY 1
    ORDER BY 2 DESC
    """

    return pd.read_sql(query, conn)

# --- Load data ---
df_path = load_path_data(start_date, end_date)

# --- Show table ---
st.subheader("🔀Squid Activity by Path")
df_display = df_path.copy()
df_display.index = df_display.index + 1
df_display = df_display.applymap(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
st.dataframe(df_display, use_container_width=True)

# --- Query Function: Row 8 --------------------------------------------------------------------------------------
@st.cache_data
def load_new_total_users(timeframe, start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    timeframe_map = {
        "day": "day",
        "week": "week",
        "month": "month"
    }
    date_trunc_unit = timeframe_map.get(timeframe, "week")

    query = f"""
    WITH overview AS (
        WITH axelar_service AS (
          SELECT created_at, recipient_address AS user
          FROM axelar.axelscan.fact_transfers
          WHERE status = 'executed' AND simplified_status = 'received'
            AND (
              sender_address ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' OR
              sender_address ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%' OR
              sender_address ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%' OR
              sender_address ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%' OR
              sender_address ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
            )
          UNION ALL
          SELECT created_at, data:call.transaction.from::STRING AS user
          FROM axelar.axelscan.fact_gmp
          WHERE status = 'executed' AND simplified_status = 'received'
            AND (
              data:approved:returnValues:contractAddress ILIKE '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%' OR
              data:approved:returnValues:contractAddress ILIKE '%0x492751eC3c57141deb205eC2da8bFcb410738630%' OR
              data:approved:returnValues:contractAddress ILIKE '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%' OR
              data:approved:returnValues:contractAddress ILIKE '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%' OR
              data:approved:returnValues:contractAddress ILIKE '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
            )
        )
        SELECT user, MIN(created_at::date) AS first_date
        FROM axelar_service
        GROUP BY user
    )
    SELECT 
      date_trunc('{date_trunc_unit}', first_date) AS "Date",
      COUNT(DISTINCT user) AS "New Users",
      SUM(COUNT(DISTINCT user)) OVER (ORDER BY date_trunc('{date_trunc_unit}', first_date)) AS "Total New Users"
    FROM overview
    WHERE first_date >= '{start_str}' AND first_date <= '{end_str}'
    GROUP BY 1
    ORDER BY 1
    """

    df = pd.read_sql(query, conn)
    return df


# --- Load Data ----------------------------------------------------------------------------------------------------
df_users = load_new_total_users(timeframe, start_date, end_date)

# --- Plotly Chart -------------------------------------------------------------------------------------------------
fig = go.Figure()

fig.add_trace(go.Bar(
    x=df_users["Date"],
    y=df_users["New Users"],
    name="New Users",
    yaxis="y1",
    marker_color="#e2fb43"  
))

fig.add_trace(go.Scatter(
    x=df_users["Date"],
    y=df_users["Total New Users"],
    name="Total New Users",
    yaxis="y2",
    mode="lines+markers",
    line=dict(color="#ca99e5", width=2)  
))

fig.update_layout(
    title="New/Total Squid Users Over Time",
    xaxis=dict(title="Date"),
    yaxis=dict(
        title="New Users",
        showgrid=False,
        zeroline=False,
        side='left'
    ),
    yaxis2=dict(
        title="Total New Users",
        overlaying='y',
        side='right',
        showgrid=False,
        zeroline=False
    ),
    legend=dict(x=0.01, y=0.99),
    bargap=0.2,
    template="plotly_white",
    height=500
)

st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------------------------------------------------------------------------------
@st.cache_data
def load_user_distribution_by_volume(start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH overview as (
      WITH axelar_service AS (
        SELECT created_at, recipient_address AS user, CASE 
            WHEN IS_ARRAY(data:send:amount) OR IS_ARRAY(data:link:price) THEN NULL
            WHEN IS_OBJECT(data:send:amount) OR IS_OBJECT(data:link:price) THEN NULL
            WHEN TRY_TO_DOUBLE(data:send:amount::STRING) IS NOT NULL AND TRY_TO_DOUBLE(data:link:price::STRING) IS NOT NULL 
              THEN TRY_TO_DOUBLE(data:send:amount::STRING) * TRY_TO_DOUBLE(data:link:price::STRING)
            ELSE NULL
          END AS amount_usd
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed' AND simplified_status = 'received'
          AND (
          sender_address ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          or sender_address ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          or sender_address ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          or sender_address ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          or sender_address ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
          AND created_at::date >= '{start_str}' AND created_at::date <= '{end_str}'

        UNION ALL

        SELECT  
          created_at,
          data:call.transaction.from::STRING AS user, CASE 
            WHEN IS_ARRAY(data:value) OR IS_OBJECT(data:value) THEN NULL
            WHEN TRY_TO_DOUBLE(data:value::STRING) IS NOT NULL THEN TRY_TO_DOUBLE(data:value::STRING)
            ELSE NULL
          END AS amount_usd
        FROM axelar.axelscan.fact_gmp 
        WHERE status = 'executed' AND simplified_status = 'received'
          AND (
              data:approved:returnValues:contractAddress ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
              or data:approved:returnValues:contractAddress ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
              or data:approved:returnValues:contractAddress ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
              or data:approved:returnValues:contractAddress ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
              or data:approved:returnValues:contractAddress ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
          AND created_at::date >= '{start_str}' AND created_at::date <= '{end_str}'
      )
      SELECT user, 
        CASE 
          WHEN SUM(amount_usd) <= 100 THEN 'a/ below 100$'
          WHEN SUM(amount_usd) > 100 AND SUM(amount_usd) <= 1000 THEN 'b/ 100-1k$'
          WHEN SUM(amount_usd) > 1000 AND SUM(amount_usd) <= 10000 THEN 'c/ 1k-10k$'
          WHEN SUM(amount_usd) > 10000 AND SUM(amount_usd) <= 100000 THEN 'd/ 10k-100k$'
          WHEN SUM(amount_usd) > 100000 AND SUM(amount_usd) <= 1000000 THEN 'e/ 100k-1M$'
          WHEN SUM(amount_usd) > 1000000 THEN 'f/ 1M+$'
        END AS "Class"
      FROM axelar_service
      GROUP BY user
    )
    SELECT "Class", COUNT(DISTINCT user) AS "Number of Users"
    FROM overview
    WHERE "Class" IS NOT NULL
    GROUP BY 1
    ORDER BY 2 DESC
    """

    df = pd.read_sql(query, conn)
    return df

@st.cache_data
def load_user_distribution_by_active_days(start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    query = f"""
    WITH overview as (
      WITH axelar_service AS (
        SELECT created_at, recipient_address AS user, id
        FROM axelar.axelscan.fact_transfers
        WHERE status = 'executed' AND simplified_status = 'received'
          AND (
          sender_address ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
          or sender_address ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
          or sender_address ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
          or sender_address ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
          or sender_address ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
          AND created_at::date >= '{start_str}' AND created_at::date <= '{end_str}'

        UNION ALL

        SELECT  
          created_at,
          data:call.transaction.from::STRING AS user, id
        FROM axelar.axelscan.fact_gmp 
        WHERE status = 'executed' AND simplified_status = 'received'
          AND (
              data:approved:returnValues:contractAddress ilike '%0xce16F69375520ab01377ce7B88f5BA8C48F8D666%'
              or data:approved:returnValues:contractAddress ilike '%0x492751eC3c57141deb205eC2da8bFcb410738630%'
              or data:approved:returnValues:contractAddress ilike '%0xDC3D8e1Abe590BCa428a8a2FC4CfDbD1AcF57Bd9%'
              or data:approved:returnValues:contractAddress ilike '%0xdf4fFDa22270c12d0b5b3788F1669D709476111E%'
              or data:approved:returnValues:contractAddress ilike '%0xe6B3949F9bBF168f4E3EFc82bc8FD849868CC6d8%'
          )
          AND created_at::date >= '{start_str}' AND created_at::date <= '{end_str}'
      )
      SELECT user, COUNT(DISTINCT DATE(created_at)) AS active_days_count,
        CASE 
          WHEN COUNT(DISTINCT DATE(created_at)) = 1 THEN 'a/ 1 Day'
          WHEN COUNT(DISTINCT DATE(created_at)) BETWEEN 2 AND 5 THEN 'b/ 2-5 Days'
          WHEN COUNT(DISTINCT DATE(created_at)) BETWEEN 6 AND 10 THEN 'c/ 6-10 Days'
          WHEN COUNT(DISTINCT DATE(created_at)) BETWEEN 11 AND 25 THEN 'd/ 11-25 Days'
          WHEN COUNT(DISTINCT DATE(created_at)) BETWEEN 26 AND 50 THEN 'e/ 26-50 Days'
          WHEN COUNT(DISTINCT DATE(created_at)) >= 51 THEN 'f/ 51+ Days'
        END AS "Number of Active Days"
      FROM axelar_service
      GROUP BY user
    )
    SELECT "Number of Active Days", COUNT(DISTINCT user) AS "Number of Users"
    FROM overview
    GROUP BY 1
    ORDER BY 2 DESC
    """

    df = pd.read_sql(query, conn)
    return df


# --- Load Data ----------------------------------------------------------------------------------------------------
df_volume = load_user_distribution_by_volume(start_date, end_date)
df_active_days = load_user_distribution_by_active_days(start_date, end_date)


# --- Plotly Donut Charts ------------------------------------------------------------------------------------------

colors_volume = ['#ca99e5', '#b083d1', '#8f62b7', '#6e429d', '#512c80', '#3b2062']
colors_active_days = ['#e2fb43', '#c8df39', '#abb62f', '#8f8d27', '#746720', '#5b5218']

fig_volume = go.Figure(data=[go.Pie(
    labels=df_volume["Class"],
    values=df_volume["Number of Users"],
    hole=0.5,
    marker_colors=colors_volume,
    sort=False,
    textinfo='label+percent'
)])

fig_volume.update_layout(
    title_text="Distribution of Squid Users By Volume",
    margin=dict(t=50, b=0, l=0, r=0)
)

fig_active_days = go.Figure(data=[go.Pie(
    labels=df_active_days["Number of Active Days"],
    values=df_active_days["Number of Users"],
    hole=0.5,
    marker_colors=colors_active_days,
    sort=False,
    textinfo='label+percent'
)])

fig_active_days.update_layout(
    title_text="Distribution of Squid Users By Number of Active Days",
    margin=dict(t=50, b=0, l=0, r=0)
)

# --- Display side by side -----------------------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(fig_volume, use_container_width=True)

with col2:
    st.plotly_chart(fig_active_days, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# --- Reference and Rebuild Info ---------------------------------------------------------------------------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 20px; margin-bottom: 20px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <img src="https://cdn-icons-png.flaticon.com/512/3178/3178287.png" alt="Reference" style="width:20px; height:20px;">
            <span>Dashboard Reference: <a href="https://flipsidecrypto.xyz/pine/squid-bridge-metrics-7jeGid" target="_blank">https://flipsidecrypto.xyz/pine/squid-bridge-metrics-7jeGid/</a></span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/1856738793325268992/OouKI10c_400x400.jpg" alt="Flipside" style="width:25px; height:25px; border-radius: 50%;">
            <span>Data Powered by: <a href="https://flipsidecrypto.xyz/home/" target="_blank">Flipside</a></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Links with Logos ---
st.markdown(
    """
    <div style="font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://axelarscan.io/logos/logo.png" alt="Axelar" style="width:20px; height:20px;">
            <a href="https://www.axelar.network/" target="_blank">Axelar Website</a>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://axelarscan.io/logos/accounts/squid.svg" alt="Squid" style="width:20px; height:20px;">
            <a href="https://www.squidrouter.com/" target="_blank">Squid Website</a>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://axelarscan.io/logos/logo.png" alt="X" style="width:20px; height:20px;">
            <a href="https://x.com/axelar" target="_blank">Axelar X Account</a>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://axelarscan.io/logos/accounts/squid.svg" alt="X" style="width:20px; height:20px;">
            <a href="https://x.com/squidrouter" target="_blank">Squid X Account</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
