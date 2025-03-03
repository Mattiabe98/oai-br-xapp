import time
import os
import pdb
import csv
import sys
import signal

cur_dir = os.path.dirname(os.path.abspath(__file__))
# print("Current Directory:", cur_dir)
sdk_path = cur_dir
sys.path.append(sdk_path)

import xapp_sdk as ric
from prometheus_client import start_http_server, Gauge, Summary

####################
#### PROMETHEUS METRICS
####################
# Create a Summary to track latencies
LATENCY_MAC = Summary('ric_mac_latency_us', 'Latency of MAC indications in microseconds')
LATENCY_RLC = Summary('ric_rlc_latency_us', 'Latency of RLC indications in microseconds')
LATENCY_PDCP = Summary('ric_pdcp_latency_us', 'Latency of PDCP indications in microseconds')
LATENCY_GTP = Summary('ric_gtp_latency_us', 'Latency of GTP indications in microseconds')

# Create Gauges for MAC metrics
MAC_DL_BER = Gauge('ric_mac_dl_ber', 'MAC DL BER', ['ue_id'])
MAC_UL_BER = Gauge('ric_mac_ul_ber', 'MAC UL BER', ['ue_id'])
MAC_BSR = Gauge('ric_mac_bsr', 'MAC BSR', ['ue_id'])
MAC_WB_CQI = Gauge('ric_mac_wb_cqi', 'MAC WB CQI', ['ue_id'])
MAC_DL_SCHED_RB = Gauge('ric_mac_dl_sched_rb', 'MAC DL Scheduled RBs', ['ue_id'])
MAC_UL_SCHED_RB = Gauge('ric_mac_ul_sched_rb', 'MAC UL Scheduled RBs', ['ue_id'])
MAC_PUSCH_SNR = Gauge('ric_mac_pusch_snr', 'MAC PUSCH SNR', ['ue_id'])
MAC_PUCCH_SNR = Gauge('ric_mac_pucch_snr', 'MAC PUCCH SNR', ['ue_id'])
MAC_DL_AGGR_PRB = Gauge('ric_mac_dl_aggr_prb', 'MAC DL Aggregated PRBs', ['ue_id'])
MAC_UL_AGGR_PRB = Gauge('ric_mac_ul_aggr_prb', 'MAC UL Aggregated PRBs', ['ue_id'])
MAC_DL_MCS1 = Gauge('ric_mac_dl_mcs1', 'MAC DL MCS1', ['ue_id'])
MAC_DL_MCS2 = Gauge('ric_mac_dl_mcs2', 'MAC DL MCS2', ['ue_id'])
MAC_UL_MCS1 = Gauge('ric_mac_ul_mcs1', 'MAC UL MCS1', ['ue_id'])
MAC_UL_MCS2 = Gauge('ric_mac_ul_mcs2', 'MAC UL MCS2', ['ue_id'])


# Create Gauges for RLC metrics
RLC_TX_RETX_PKTS = Gauge('ric_rlc_tx_retx_pkts', 'RLC PDU TX Retransmitted Packets', ['ue_id'])
RLC_TX_DROPPED_PKTS = Gauge('ric_rlc_tx_dropped_pkts', 'RLC PDU TX Dropped Packets', ['ue_id'])

# Create Gauges for PDCP metrics
PDCP_TX_BYTES = Gauge('ric_pdcp_tx_bytes', 'PDCP Total TX PDU Bytes', ['ue_id'])
PDCP_RX_BYTES = Gauge('ric_pdcp_rx_bytes', 'PDCP Total RX PDU Bytes', ['ue_id'])

# Create Gauges for GTP metrics
GTP_QFI = Gauge('ric_gtp_qfi', 'GTP QoS Flow Indicator', ['ue_id'])
GTP_TEID = Gauge('ric_gtp_teid', 'GTP gNB Tunnel Identifier', ['ue_id'])

running = True

def handle_sigterm(signum, frame):
    global running
    print("Received SIGTERM, shutting down...")
    running = False  # Stop the main loop


####################
#### MAC INDICATION CALLBACK
####################

# MACCallback class is defined and derived from C++ class mac_cb
class MACCallback(ric.mac_cb):
    # Define Python class 'constructor'
    def __init__(self):
        # Call C++ base class constructor
        ric.mac_cb.__init__(self)
    # Override C++ method: virtual void handle(swig_mac_ind_msg_t a) = 0;
    def handle(self, ind):
        # Print swig_mac_ind_msg_t
        if len(ind.ue_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_mac = ind.tstamp / 1.0
            t_diff = t_now - t_mac

            # Update Prometheus metrics
            LATENCY_MAC.observe(t_diff)
            for id, ue in enumerate(ind.ue_stats):
                MAC_DL_BER.labels(ue_id=id).set(ue.dl_bler)
                MAC_UL_BER.labels(ue_id=id).set(ue.ul_bler)
                MAC_BSR.labels(ue_id=id).set(ue.bsr)
                MAC_WB_CQI.labels(ue_id=id).set(ue.wb_cqi)
                MAC_DL_SCHED_RB.labels(ue_id=id).set(ue.dl_sched_rb)
                MAC_UL_SCHED_RB.labels(ue_id=id).set(ue.ul_sched_rb)
                MAC_PUSCH_SNR.labels(ue_id=id).set(ue.pusch_snr)
                MAC_PUCCH_SNR.labels(ue_id=id).set(ue.pucch_snr)
                MAC_DL_AGGR_PRB.labels(ue_id=id).set(ue.dl_aggr_prb)
                MAC_UL_AGGR_PRB.labels(ue_id=id).set(ue.ul_aggr_prb)
                MAC_DL_MCS1.labels(ue_id=id).set(ue.dl_mcs1)
                MAC_UL_MCS1.labels(ue_id=id).set(ue.ul_mcs1)
                MAC_DL_MCS2.labels(ue_id=id).set(ue.dl_mcs2)
                MAC_UL_MCS2.labels(ue_id=id).set(ue.ul_mcs2)


            #print(f"MAC Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            # with open(file_name, 'a', newline='', buffering=1024) as f:
            #     writer = csv.writer(f)
            #     writer.writerow([ind.id.nb_id.nb_id, ind.id.type, "MAC", t_diff])
            # print('MAC rnti = ' + str(ind.ue_stats[0].rnti))

####################
#### RLC INDICATION CALLBACK
####################

class RLCCallback(ric.rlc_cb):
    # Define Python class 'constructor'
    def __init__(self):
        # Call C++ base class constructor
        ric.rlc_cb.__init__(self)
    # Override C++ method: virtual void handle(swig_rlc_ind_msg_t a) = 0;
    def handle(self, ind):
        # Print swig_rlc_ind_msg_t
        if len(ind.rb_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_rlc = ind.tstamp / 1.0
            t_diff= t_now - t_rlc

            # Update Prometheus metrics
            LATENCY_RLC.observe(t_diff)

            #print(f"RLC Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            # with open(file_name, 'a', newline='', buffering=1024) as f:
            #     writer = csv.writer(f)
            #     writer.writerow([ind.id.nb_id.nb_id, ind.id.type, "RLC", t_diff])
            # print('RLC rnti = '+ str(ind.rb_stats[0].rnti))
            for id, rb in enumerate(ind.rb_stats):
                RLC_TX_RETX_PKTS.labels(ue_id=id).set(rb.txpdu_retx_pkts)
                RLC_TX_DROPPED_PKTS.labels(ue_id=id).set(rb.txpdu_dd_pkts)

####################
#### PDCP INDICATION CALLBACK
####################

class PDCPCallback(ric.pdcp_cb):
    # Define Python class 'constructor'
    def __init__(self):
        # Call C++ base class constructor
        ric.pdcp_cb.__init__(self)
   # Override C++ method: virtual void handle(swig_pdcp_ind_msg_t a) = 0;
    def handle(self, ind):
        # Print swig_pdcp_ind_msg_t
        if len(ind.rb_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_pdcp = ind.tstamp / 1.0
            t_diff = t_now - t_pdcp

            # Update Prometheus metrics
            LATENCY_PDCP.observe(t_diff)

            #print(f"PDCP Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            # with open(file_name, 'a', newline='', buffering=1024) as f:
            #     writer = csv.writer(f)
            #     writer.writerow([ind.id.nb_id.nb_id, ind.id.type, "PDCP", t_diff])
            # print('PDCP rnti = '+ str(ind.rb_stats[0].rnti))
            for id, rb in enumerate(ind.rb_stats):
                PDCP_TX_BYTES.labels(ue_id=id).set(rb.txpdu_bytes)
                PDCP_RX_BYTES.labels(ue_id=id).set(rb.rxpdu_bytes)

####################
#### GTP INDICATION CALLBACK
####################

# Create a callback for GTP which derived it from C++ class gtp_cb
class GTPCallback(ric.gtp_cb):
    def __init__(self):
        # Inherit C++ gtp_cb class
        ric.gtp_cb.__init__(self)
    # Create an override C++ method
    def handle(self, ind):
        if len(ind.gtp_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_gtp = ind.tstamp / 1.0
            t_diff = t_now - t_gtp

            # Update Prometheus metrics
            LATENCY_GTP.observe(t_diff)

            #print(f"GTP Indication tstamp {t_now} diff {t_diff} e2 node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            for id, stat in enumerate(ind.gtp_stats):
                GTP_QFI.labels(ue_id=id).set(stat.qfi)
                GTP_TEID.labels(ue_id=id).set(stat.teidgnb)

####################
#### SLICE INDICATION CALLBACK
####################

# Create a callback for SLICE which derived it from C++ class slice_cb
class SLICECallback(ric.slice_cb):
    def __init__(self):
        # Inherit C++ gtp_cb class
        ric.slice_cb.__init__(self)
    # Create an override C++ method
    def handle(self, ind):
        t_now = time.time_ns() / 1000.0
        t_slice = ind.tstamp / 1.0
        t_diff = t_now - t_slice
        #print(f"SLICE Indication tstamp {t_now} diff {t_diff} e2 node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")


def get_cust_tti(tti):
    if tti == "1_ms":
        return ric.Interval_ms_1
    elif tti == "2_ms":
        return ric.Interval_ms_2
    elif tti == "5_ms":
        return ric.Interval_ms_5
    elif tti == "10_ms":
        return ric.Interval_ms_10
    elif tti == "100_ms":
        return ric.Interval_ms_100
    elif tti == "1000_ms":
        return ric.Interval_ms_1000
    else:
        print(f"Unknown tti {tti}")
        exit()

mac_hndlr = []
rlc_hndlr = []
pdcp_hndlr = []
gtp_hndlr = []
slice_hndlr = []
####################
####  GENERAL
####################
if __name__ == '__main__':

    # file_name = "ind_output.csv"
    # file_col = ['e2node-nb-id', 'e2node-ran-type', 'SM', 'latency']
    # if file already exists, remove it
    # if os.path.exists(file_name):
    #     os.remove(file_name)
    # # create new csv file and write headers
    # with open(file_name, 'w', newline='') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(file_col)

    # Start
    signal.signal(signal.SIGTERM, handle_sigterm)
    ric.init(sys.argv)

    # Start Prometheus Exporter
    start_http_server(8000)

    cust_sm = ric.get_cust_sm_conf()

    conn = ric.conn_e2_nodes()
    assert(len(conn) > 0)
    for i in range(0, len(conn)):
        print("Global E2 Node [" + str(i) + "]: PLMN MCC = " + str(conn[i].id.plmn.mcc) + " MNC = " + str(conn[i].id.plmn.mnc) + " Type: " + str(conn[i].id.type))

        try:
            print("CU-DU ID: " + str(conn[i].id.cu_du_id))
        except:
            print("No CU-DU ID!")
    for sm_info in cust_sm:
        sm_name = sm_info.name
        sm_time = sm_info.time
        tti = get_cust_tti(sm_time)

        if sm_name == "MAC":
            for i in range(0, len(conn)):
                # MAC
                mac_cb = MACCallback()
                hndlr = ric.report_mac_sm(conn[i].id, tti, mac_cb)
                mac_hndlr.append(hndlr)
                time.sleep(1)
        elif sm_name == "RLC":
            for i in range(0, len(conn)):
                # RLC
                rlc_cb = RLCCallback()
                hndlr = ric.report_rlc_sm(conn[i].id, tti, rlc_cb)
                rlc_hndlr.append(hndlr)
                time.sleep(1)
        elif sm_name == "PDCP":
            for i in range(0, len(conn)):
                # PDCP
                pdcp_cb = PDCPCallback()
                hndlr = ric.report_pdcp_sm(conn[i].id, tti, pdcp_cb)
                pdcp_hndlr.append(hndlr)
                time.sleep(1)
        elif sm_name == "GTP":
            for i in range(0, len(conn)):
                # GTP
                gtp_cb = GTPCallback()
                hndlr = ric.report_gtp_sm(conn[i].id, tti, gtp_cb)
                gtp_hndlr.append(hndlr)
                time.sleep(1)
        elif sm_name == "SLICE":
            for i in range(0, len(conn)):
                # SLICE
                slice_cb = SLICECallback()
                hndlr = ric.report_slice_sm(conn[i].id, tti, slice_cb)
                slice_hndlr.append(hndlr)
                time.sleep(1)
        else:
            print(f"not yet implemented function to send subscription for {sm_name}")
    while running:
        time.sleep(1)

    print("Cleaning up resources...", flush=True)
    ### End
    for i in range(0, len(mac_hndlr)):
        ric.rm_report_mac_sm(mac_hndlr[i])

    for i in range(0, len(rlc_hndlr)):
        ric.rm_report_rlc_sm(rlc_hndlr[i])

    for i in range(0, len(pdcp_hndlr)):
        ric.rm_report_pdcp_sm(pdcp_hndlr[i])

    for i in range(0, len(gtp_hndlr)):
        ric.rm_report_gtp_sm(gtp_hndlr[i])

    for i in range(0, len(slice_hndlr)):
        ric.rm_report_slice_sm(slice_hndlr[i])

    time.sleep(2)
    # Avoid deadlock. ToDo revise architecture
    while ric.try_stop == 0:
        time.sleep(1)

    print("Cleanup completed. Exiting.", flush=True)
