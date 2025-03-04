import time
import os
import pdb
from tabulate import tabulate
import signal
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
# print("Current Directory:", cur_dir)
sdk_path = cur_dir + "/../xapp_sdk/"
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
LATENCY_KPM = Summary('ric_kpm_latency_us', 'Latency of KPM indications in microseconds')


# Create Gauges for MAC metrics
MAC_DL_BER = Gauge('ric_mac_dl_ber', 'MAC DL BER', ['e2node', 'ue_id'])
MAC_UL_BER = Gauge('ric_mac_ul_ber', 'MAC UL BER', ['e2node', 'ue_id'])
MAC_BSR = Gauge('ric_mac_bsr', 'MAC BSR', ['e2node', 'ue_id'])
MAC_WB_CQI = Gauge('ric_mac_wb_cqi', 'MAC WB CQI', ['e2node', 'ue_id'])
MAC_DL_SCHED_RB = Gauge('ric_mac_dl_sched_rb', 'MAC DL Scheduled RBs', ['e2node', 'ue_id'])
MAC_UL_SCHED_RB = Gauge('ric_mac_ul_sched_rb', 'MAC UL Scheduled RBs', ['e2node', 'ue_id'])
MAC_PUSCH_SNR = Gauge('ric_mac_pusch_snr', 'MAC PUSCH SNR', ['e2node', 'ue_id'])
MAC_PUCCH_SNR = Gauge('ric_mac_pucch_snr', 'MAC PUCCH SNR', ['e2node', 'ue_id'])
MAC_DL_AGGR_PRB = Gauge('ric_mac_dl_aggr_prb', 'MAC DL Aggregated PRBs', ['e2node', 'ue_id'])
MAC_UL_AGGR_PRB = Gauge('ric_mac_ul_aggr_prb', 'MAC UL Aggregated PRBs', ['e2node', 'ue_id'])
MAC_DL_MCS1 = Gauge('ric_mac_dl_mcs1', 'MAC DL MCS1', ['e2node', 'ue_id'])
MAC_DL_MCS2 = Gauge('ric_mac_dl_mcs2', 'MAC DL MCS2', ['e2node', 'ue_id'])
MAC_UL_MCS1 = Gauge('ric_mac_ul_mcs1', 'MAC UL MCS1', ['e2node', 'ue_id'])
MAC_UL_MCS2 = Gauge('ric_mac_ul_mcs2', 'MAC UL MCS2', ['e2node', 'ue_id'])

# Create Gauges for RLC metrics
RLC_TX_RETX_PKTS = Gauge('ric_rlc_tx_retx_pkts', 'RLC PDU TX Retransmitted Packets', ['e2node', 'ue_id'])
RLC_TX_DROPPED_PKTS = Gauge('ric_rlc_tx_dropped_pkts', 'RLC PDU TX Dropped Packets', ['e2node', 'ue_id'])

# Create Gauges for PDCP metrics
PDCP_TX_BYTES = Gauge('ric_pdcp_tx_bytes', 'PDCP Total TX PDU Bytes', ['e2node', 'ue_id'])
PDCP_RX_BYTES = Gauge('ric_pdcp_rx_bytes', 'PDCP Total RX PDU Bytes', ['e2node', 'ue_id'])

# KPM Metrics (Example - Adapt based on KPM indication content)
KPM_PRB_DL = Gauge('ric_kpm_prb_dl', 'KPM PRB DL', ['e2node', 'ue_id'])
KPM_PRB_UL = Gauge('ric_kpm_prb_ul', 'KPM PRB UL', ['e2node', 'ue_id'])


def gen_id_key(id):
    plmn = "PLMN_" + str(id.plmn.mcc) + str(id.plmn.mnc)
    nb_id = "NBID_" + str(id.nb_id.nb_id)
    ran_type = get_ngran_name(id.type)
    return plmn + "-" + nb_id + "-" + ran_type

def sig_handler(signum, frame):
    print("Ctrl-C Detect")

    conn = ric.conn_e2_nodes()
    for n in conn:
        key = gen_id_key(n.id)
        if key in mac_hndlr:
            for i in range(0, len(mac_hndlr[key])):
                ric.rm_report_mac_sm(mac_hndlr[key][i])
        if key in rlc_hndlr:
            for i in range(0, len(rlc_hndlr[key])):
                ric.rm_report_rlc_sm(rlc_hndlr[key][i])
        if key in pdcp_hndlr:
            for i in range(0, len(pdcp_hndlr[key])):
                ric.rm_report_pdcp_sm(pdcp_hndlr[key][i])
        if key in gtp_hndlr:
            for i in range(0, len(gtp_hndlr[key])):
                ric.rm_report_gtp_sm(gtp_hndlr[key][i])                
        if key in kpm_hndlr:
            for i in range(0, len(kpm_hndlr[key])):
                ric.rm_report_kpm_sm(kpm_hndlr[key][i])

    # Avoid deadlock. ToDo revise architecture
    while ric.try_stop == 0:
        time.sleep(1)

    print("Test finished")
    exit(1)


####################
#### MAC INDICATION CALLBACK
####################
#  MACCallback class is defined and derived from C++ class mac_cb
class MACCallback(ric.mac_cb):
    # Define Python class 'constructor'
    def __init__(self):
        # Call C++ base class constructor
        ric.mac_cb.__init__(self)
    # Override C++ method: virtual void handle(swig_mac_ind_msg_t a) = 0;
    def handle(self, ind):
        # Print swig_mac_ind_msg_t
        e2node_key = gen_id_key(ind.id)

        if len(ind.ue_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_mac = ind.tstamp / 1.0
            t_diff = t_now - t_mac

            # Update Prometheus metrics
            LATENCY_MAC.observe(t_diff)

            #print(f"MAC Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            for id, ue in enumerate(ind.ue_stats):
                MAC_DL_BER.labels(e2node=e2node_key, ue_id=id).set(ue.dl_bler)
                MAC_UL_BER.labels(e2node=e2node_key, ue_id=id).set(ue.ul_bler)
                MAC_BSR.labels(e2node=e2node_key, ue_id=id).set(ue.bsr)
                MAC_WB_CQI.labels(e2node=e2node_key, ue_id=id).set(ue.wb_cqi)
                MAC_DL_SCHED_RB.labels(e2node=e2node_key, ue_id=id).set(ue.dl_sched_rb)
                MAC_UL_SCHED_RB.labels(e2node=e2node_key, ue_id=id).set(ue.ul_sched_rb)
                MAC_PUSCH_SNR.labels(e2node=e2node_key, ue_id=id).set(ue.pusch_snr)
                MAC_PUCCH_SNR.labels(e2node=e2node_key, ue_id=id).set(ue.pucch_snr)
                MAC_DL_AGGR_PRB.labels(e2node=e2node_key, ue_id=id).set(ue.dl_aggr_prb)
                MAC_UL_AGGR_PRB.labels(e2node=e2node_key, ue_id=id).set(ue.ul_aggr_prb)
                MAC_DL_MCS1.labels(e2node=e2node_key, ue_id=id).set(ue.dl_mcs1)
                MAC_UL_MCS1.labels(e2node=e2node_key, ue_id=id).set(ue.ul_mcs1)
                MAC_DL_MCS2.labels(e2node=e2node_key, ue_id=id).set(ue.dl_mcs2)
                MAC_UL_MCS2.labels(e2node=e2node_key, ue_id=id).set(ue.ul_mcs2)
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
        e2node_key = gen_id_key(ind.id)

        if len(ind.rb_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_rlc = ind.tstamp / 1.0
            t_diff = t_now - t_rlc

            # Update Prometheus metrics
            LATENCY_RLC.observe(t_diff)

            #print(f"RLC Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            for id, rb in enumerate(ind.rb_stats):
                RLC_TX_RETX_PKTS.labels(e2node=e2node_key, ue_id=id).set(rb.txpdu_retx_pkts)
                RLC_TX_DROPPED_PKTS.labels(e2node=e2node_key, ue_id=id).set(rb.txpdu_dd_pkts)


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
        e2node_key = gen_id_key(ind.id)

        if len(ind.rb_stats) > 0:
            t_now = time.time_ns() / 1000.0
            t_pdcp = ind.tstamp / 1.0
            t_diff = t_now - t_pdcp

            # Update Prometheus metrics
            LATENCY_PDCP.observe(t_diff)

            #print(f"PDCP Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            # print('PDCP rnti = '+ str(ind.rb_stats[0].rnti))
            for id, rb in enumerate(ind.rb_stats):
                PDCP_TX_BYTES.labels(e2node=e2node_key, ue_id=id).set(rb.txpdu_bytes)
                PDCP_RX_BYTES.labels(e2node=e2node_key, ue_id=id).set(rb.rxpdu_bytes)

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
        e2node_key = gen_id_key(ind.id)
        
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
#### KPM INDICATION CALLBACK
####################
# Create a callback for KPM which derived it from C++ class kpm_cb
class KPMCallback(ric.kpm_cb):
    def __init__(self):
        # Inherit C++ kpm_cb class
        ric.kpm_cb.__init__(self)
    # Create an override C++ method
    def handle(self, ind):

        e2node_key = gen_id_key(ind.id)

        if ind.hdr:
            t_now = time.time_ns() / 1000.0
            t_kpm = ind.hdr.kpm_ric_ind_hdr_format_1.collectStartTime / 1.0
            t_diff = t_now - t_kpm

            # Update Prometheus metrics
            LATENCY_KPM.observe(t_diff)

            #print(f"KPM Indication tstamp {t_now} diff {t_diff} E2-node type {ind.id.type} nb_id {ind.id.nb_id.nb_id}")
            # if ind.hdr.kpm_ric_ind_hdr_format_1.fileformat_version:
            #     print(f"fileformat_version {ind.hdr.kpm_ric_ind_hdr_format_1.fileformat_version}")
            # if ind.hdr.kpm_ric_ind_hdr_format_1.sender_name:
            #     print(f"sender_name {ind.hdr.kpm_ric_ind_hdr_format_1.sender_name}")
            # if ind.hdr.kpm_ric_ind_hdr_format_1.sender_type:
            #     print(f"sender_type {ind.hdr.kpm_ric_ind_hdr_format_1.sender_type}")
            # if ind.hdr.kpm_ric_ind_hdr_format_1.vendor_name:
            #     print(f"vendor_name {ind.hdr.kpm_ric_ind_hdr_format_1.vendor_name}")
        if ind.msg.type == ric.FORMAT_1_INDICATION_MESSAGE:
            ind_frm1 = ind.msg.frm_1
            # print(f"ind_frm1.meas_data_lst_len {ind_frm1.meas_data_lst_len}")
            for index, meas_data in enumerate(ind_frm1.meas_data_lst):
                # print(f"meas data idx {index}")
                if meas_data.incomplete_flag == ric.TRUE_ENUM_VALUE:
                    print(f"<<< Measurement Record not reliable >>> ")
                if meas_data.meas_record_len == ind_frm1.meas_info_lst_len:
                    # print(f"meas_data.meas_record_len {meas_data.meas_record_len}, ind_frm1.meas_info_lst_len {ind_frm1.meas_info_lst_len}")
                    for meas_record, meas_info in zip(meas_data.meas_record_lst, ind_frm1.meas_info_lst):
                        # print(f"value: {meas_record.value}")
                        # print(f"type: {meas_info.meas_type.type}")
                        print_value = 0
                        if meas_record.value == ric.INTEGER_MEAS_VALUE:
                            print_value = meas_record.int_val
                        elif meas_record.value == ric.REAL_MEAS_VALUE:
                            print_value = meas_record.real_val
                        elif meas_record.value == ric.NO_VALUE_MEAS_VALUE:
                            print_value = meas_record.no_value
                        else:
                            print(f"unknown meas_record")

                        print_name_id = 0
                        if meas_info.meas_type.type == ric.NAME_MEAS_TYPE:
                            print_name_id = meas_info.meas_type.name
                        elif meas_info.meas_type.type == ric.ID_MEAS_TYPE:
                            print_name_id = meas_info.meas_type.id
                        else:
                            print(f"unknown meas info type")

                        # Export some KPM metrics to Prometheus (Adapt based on your needs)
                        if print_name_id == "RRU.PrbTotDl":  # Example metric
                            KPM_PRB_DL.labels(e2node=e2node_key, ue_id="N/A").set(print_value)
                        if print_name_id == "RRU.PrbTotUl":  # Example metric
                            KPM_PRB_UL.labels(e2node=e2node_key, ue_id="N/A").set(print_value)
                        # print(f"Measurement name/id:value {print_name_id}:{print_value}")
                else:
                    print(f"meas_data.meas_record_len {meas_data.meas_record_len} != ind_frm1.meas_info_lst_len {ind_frm1.meas_info_lst_len}, cannot map value to name")

            #print(f"ind_frm1.gran_period_ms {ind_frm1.gran_period_ms}")
        elif ind.msg.type == ric.FORMAT_3_INDICATION_MESSAGE:
            # print(f"ind.msg.type {ind.msg.type}")
            # print(f"ind.msg.frm_3.ue_meas_report_lst_len {ind.msg.frm_3.ue_meas_report_lst_len}")
            for ue_meas in ind.msg.frm_3.meas_report_per_ue: # swig_meas_report_per_ue_t
                # swig_ue_id_e2sm_t
                #print(f"ue_meas.type {ue_meas.ue_meas_report_lst.type}")
                ue = ue_meas.ue_meas_report_lst
                if ue.type == ric.GNB_UE_ID_E2SM:
                    #print(f"ue.gnb.amf_ue_ngap_id {ue.gnb.amf_ue_ngap_id},"
                    #      f"ue.gnb.guami.plmn_id.mcc {ue.gnb.guami.plmn_id.mcc},"
                    #      f"ue.gnb.guami.plmn_id.mnc {ue.gnb.guami.plmn_id.mnc},"
                    #      f"ue.gnb.guami.plmn_id.mnc_digit_len {ue.gnb.guami.plmn_id.mnc_digit_len}")
                    amf_ue_ngap_id = ue.gnb.amf_ue_ngap_id
                elif ue.type == ric.GNB_DU_UE_ID_E2SM:
                    #print(f"ue.gnb_du.gnb_cu_ue_f1ap {ue.gnb_du.gnb_cu_ue_f1ap}")
                    amf_ue_ngap_id = ue.gnb_du.gnb_cu_ue_f1ap
                elif ue.type == ric.GNB_CU_UP_UE_ID_E2SM:
                    #print(f"ue.gnb_cu_up.gnb_cu_cp_ue_e1ap {ue.gnb_cu_up.gnb_cu_cp_ue_e1ap}")
                    amf_ue_ngap_id = ue.gnb_cu_up.gnb_cu_cp_ue_e1ap
                else:
                    print("python3: not support ue_id_e2sm type")
                # swig_kpm_ind_msg_format_1_t
                ind_frm1 = ue_meas.ind_msg_format_1
                #print(f"ind_frm1.meas_data_lst_len {ind_frm1.meas_data_lst_len}")
                for meas_data in ind_frm1.meas_data_lst:
                    # print(f"meas_data.meas_record_len {meas_data.meas_record_len}")
                    # for meas_record in meas_data.meas_record_lst:
                    #     # print(f"meas_record.value {meas_record.value}")
                    #     if meas_record.value == ric.INTEGER_MEAS_VALUE:
                    #         print(f"meas_record.int_val {meas_record.int_val}")
                    #     elif meas_record.value == ric.REAL_MEAS_VALUE:
                    #         print(f"meas_record.real_val {meas_record.real_val}")
                    #     elif meas_record.value == ric.NO_VALUE_MEAS_VALUE:
                    #         print(f"meas_record.no_value {meas_record.no_value}")
                    #     else:
                    #         print(f"unknown meas_record")
                    if meas_data.incomplete_flag == ric.TRUE_ENUM_VALUE:
                        print(f"<<< Measurement Record not reliable >>> ")

                    if meas_data.meas_record_len == ind_frm1.meas_info_lst_len:
                        # print(f"meas_data.meas_record_len {meas_data.meas_record_len}, ind_frm1.meas_info_lst_len {ind_frm1.meas_info_lst_len}")
                        for meas_record, meas_info in zip(meas_data.meas_record_lst, ind_frm1.meas_info_lst):
                            # print(f"value: {meas_record.value}")
                            # print(f"type: {meas_info.meas_type.type}")
                            print_value = 0
                            if meas_record.value == ric.INTEGER_MEAS_VALUE:
                                print_value = meas_record.int_val
                            elif meas_record.value == ric.REAL_MEAS_VALUE:
                                print_value = meas_record.real_val
                            elif meas_record.value == ric.NO_VALUE_MEAS_VALUE:
                                print_value = meas_record.no_value
                            else:
                                print(f"unknown meas_record")

                            print_name_id = 0
                            if meas_info.meas_type.type == ric.NAME_MEAS_TYPE:
                                print_name_id = meas_info.meas_type.name
                            elif meas_info.meas_type.type == ric.ID_MEAS_TYPE:
                                print_name_id = meas_info.meas_type.id
                            else:
                                print(f"unknown meas info type")

                            # Export some KPM metrics to Prometheus (Adapt based on your needs)
                            if print_name_id == "DRB.UEThpDl":  # Example metric
                                KPM_PRB_DL.labels(e2node=e2node_key, ue_id=amf_ue_ngap_id).set(print_value)
                            if print_name_id == "DRB.UEThpUl":  # Example metric
                                KPM_PRB_UL.labels(e2node=e2node_key, ue_id=amf_ue_ngap_id).set(print_value)
                            #print(f"Measurement name/id:value {print_name_id}:{print_value}")
                    else:
                        print(f"meas_data.meas_record_len {meas_data.meas_record_len} != ind_frm1.meas_info_lst_len {ind_frm1.meas_info_lst_len}, cannot map value to name")


                # print(f"ind_frm1.meas_info_lst_len {ind_frm1.meas_info_lst_len}")
                # for meas_info in ind_frm1.meas_info_lst:
                #     # print(f"meas_info.meas_type.type {meas_info.meas_type.type}")
                #     if meas_info.meas_type.type == ric.NAME_MEAS_TYPE:
                #         print(f"meas_info.meas_type.name {meas_info.meas_type.name}")
                #     elif meas_info.meas_type.type == ric.ID_MEAS_TYPE:
                #         print(f"meas_info.meas_type.id {meas_info.meas_type.id}")
                #     else:
                #         print(f"unknown meas info type")

                #print(f"ind_frm1.gran_period_ms {ind_frm1.gran_period_ms}")
        else:
            print(f"not implement KPM indication format {ind.msg.type}")



####################
#### UPDATE CONNECTED E2 NODES
####################
def get_e2_nodes():
    return ric.conn_e2_nodes()

####################
#### SEND SUBSCRIPTION REQUEST
####################
mac_cb = 0
rlc_cb = 0
pdcp_cb = 0
kpm_cb = 0
gtp_cb = 0
def send_mac_sub_req(id, tti):
    global mac_cb
    global mac_hndlr
    mac_cb = MACCallback()
    hndlr = ric.report_mac_sm(id, tti, mac_cb)
    key = gen_id_key(id)
    mac_hndlr.setdefault(key, []).append(hndlr)
def send_rlc_sub_req(id, tti):
    global rlc_cb
    global rlc_hndlr
    rlc_cb = RLCCallback()
    hndlr = ric.report_rlc_sm(id, tti, rlc_cb)
    key = gen_id_key(id)
    rlc_hndlr.setdefault(key, []).append(hndlr)
def send_pdcp_sub_req(id, tti):
    global pdcp_cb
    global pdcp_hndlr
    pdcp_cb = PDCPCallback()
    hndlr = ric.report_pdcp_sm(id, tti, pdcp_cb)
    key = gen_id_key(id)
    pdcp_hndlr.setdefault(key, []).append(hndlr)
def send_gtp_sub_req(id, tti):
    global gtp_cb
    global gtp_hndlr
    gtp_cb = GTPCallback()
    hndlr = ric.report_gtp_sm(id, tti, gtp_cb)
    key = gen_id_key(id)
    gtp_hndlr.setdefault(key, []).append(hndlr)
def send_kpm_sub_req(id, tti, action):
    global kpm_cb
    global kpm_hndlr
    kpm_cb = KPMCallback()
    hndlr = ric.report_kpm_sm(id, tti, action, kpm_cb)
    key = gen_id_key(id)
    kpm_hndlr.setdefault(key, []).append(hndlr)

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

def get_oran_tti(tti):
    if tti == 1:
        return ric.Interval_ms_1
    elif tti == 2:
        return ric.Interval_ms_2
    elif tti == 5:
        return ric.Interval_ms_5
    elif tti == 10:
        return ric.Interval_ms_10
    elif tti == 100:
        return ric.Interval_ms_100
    elif tti == 1000:
        return ric.Interval_ms_1000
    else:
        print(f"Unknown tti {tti}")
        exit()

def send_subscription_req(nodes, cust_sm, oran_sm):
    for sm_info in cust_sm:
        sm_name = sm_info.name
        sm_time = sm_info.time
        tti = get_cust_tti(sm_time)

        if sm_name == "MAC" and (nodes.id.type == ric.e2ap_ngran_gNB or nodes.id.type == ric.e2ap_ngran_gNB_DU or nodes.id.type == ric.e2ap_ngran_eNB):
            print(f"<<<< Subscribe to {sm_name} with time period {sm_time} >>>>")
            send_mac_sub_req(nodes.id, tti)
        elif sm_name == "RLC" and (nodes.id.type == ric.e2ap_ngran_gNB or nodes.id.type == ric.e2ap_ngran_gNB_DU or nodes.id.type == ric.e2ap_ngran_eNB):
            print(f"<<<< Subscribe to {sm_name} with time period {sm_time} >>>>")
            send_rlc_sub_req(nodes.id, tti)
        elif sm_name == "PDCP" and (nodes.id.type == ric.e2ap_ngran_gNB or nodes.id.type == ric.e2ap_ngran_gNB_CU or nodes.id.type == ric.e2ap_ngran_gNB_CUUP):
            print(f"<<<< Subscribe to {sm_name} with time period {sm_time} >>>>")
            send_pdcp_sub_req(nodes.id, tti)
        elif sm_name == "GTP" and (nodes.id.type == ric.e2ap_ngran_gNB or nodes.id.type == ric.e2ap_ngran_gNB_CU or nodes.id.type == ric.e2ap_ngran_gNB_CUUP):
            print(f"<<<< Subscribe to {sm_name} with time period {sm_time} >>>>")
            send_gtp_sub_req(nodes.id, tti)        
        else:
            print(f"not yet implemented function to send subscription for {sm_name}")

    for sm_info in oran_sm:
        sm_name = sm_info.name
        if sm_name != "KPM":
            print(f"not support {sm_name} in python")
            continue
        sm_time = sm_info.time
        tti = get_oran_tti(sm_time)
        sm_format = sm_info.format
        ran_type = sm_info.ran_type
        print("SM: " + str(sm_name) + " RAN Type: " + str(ran_type))
        print(str(nodes.id.type) + " " + str(ric.get_e2ap_ngran_name(nodes.id.type)))
        act_len = sm_info.act_len
        act = []
        for a in sm_info.actions:
            act.append(a.name)
        if nodes.id.type == ric.e2ap_ngran_eNB:
            continue
        if ran_type == ric.get_e2ap_ngran_name(nodes.id.type):
            send_kpm_sub_req(nodes.id, tti, act)


        # if nodes.id.type == ric.e2ap_ngran_gNB:
        #     send_mac_sub_req(nodes.id, tti)
        #     send_rlc_sub_req(nodes.id, tti)
        #     send_pdcp_sub_req(nodes.id, tti)
        #     action = ["DRB.PdcpSduVolumeDL", "DRB.PdcpSduVolumeUL", "DRB.RlcSduDelayDl", "DRB.UEThpDl", "DRB.UEThpUl", "RRU.PrbTotDl", "RRU.PrbTotUl"]
        #     send_kpm_sub_req(nodes.id, tti, action)
        # elif nodes.id.type == ric.e2ap_ngran_gNB_CU:
        #     send_pdcp_sub_req(nodes.id, tti)
        #     action = ["DRB.PdcpSduVolumeDL", "DRB.PdcpSduVolumeUL"]
        #     send_kpm_sub_req(nodes.id, tti, action)
        # elif nodes.id.type == ric.e2ap_ngran_gNB_DU:
        #     send_mac_sub_req(nodes.id, tti)
        #     send_rlc_sub_req(nodes.id, tti)
        #     action = ["DRB.RlcSduDelayDl", "DRB.UEThpDl", "DRB.UEThpUl", "RRU.PrbTotDl", "RRU.PrbTotUl"]
        #     send_kpm_sub_req(nodes.id, tti, action)
        # elif nodes.id.type == ric.e2ap_ngran_eNB:
        #     send_mac_sub_req(nodes.id, tti)
        #     send_rlc_sub_req(nodes.id, tti)
        #     send_pdcp_sub_req(nodes.id, tti)
        # else:
        #     print(f"NG-RAN Type {ran_type} not yet implemented\n")
        #     exit()


####################
#### GET NGRAN TYPE IN STRING
####################
def get_ngran_name(ran_type):
    if ran_type == 0:
        return "ngran_eNB"
    elif ran_type == 2:
        return "ngran_gNB"
    elif ran_type == 5:
        return "ngran_gNB_CU"
    elif ran_type == 7:
        return "ngran_gNB_DU"
    elif ran_type == 9:
        return "ngran_gNB_CUCP"
    elif ran_type == 10:
        return "ngran_gNB_CUUP"
    else:
        return "Unknown"

####################
#### PRINT E2 NODES IN TABLE
####################
e2nodes_col_names = ["idx", "nb_id", "mcc", "mnc", "ran_type"]
def print_e2_nodes():
    e2nodes_data = []
    conn = ric.conn_e2_nodes()
    for i in range(0, len(conn)):
        # TODO: need to fix cu_du_id in swig
        # cu_du_id = -1
        # if conn[i].id.cu_du_id:
        #     cu_du_id = conn[i].id.cu_du_id
        info = [conn[i].id.nb_id.nb_id,
                conn[i].id.plmn.mcc,
                conn[i].id.plmn.mnc,
                get_ngran_name(conn[i].id.type)]
        # print(info)
        e2nodes_data.append(info)
    print(tabulate(e2nodes_data, headers=e2nodes_col_names, tablefmt="grid"))
    # print("E2 node : "
    #       "nb_id " + str(e2node.id.nb_id.nb_id) + ",",
    #       "mcc " + str(e2node.id.plmn.mcc) + ",",
    #       "mnc " + str(e2node.id.plmn.mnc) + ",",
    #       "mnc_digit_len " + str(e2node.id.plmn.mnc_digit_len) + ",",
    #       "ran_type " + get_ngran_name(e2node.id.type) + ',',
    #       "cu_du_id " + str(e2node.id.cu_du_id if e2node.id.cu_du_id else -1))

####################
#### TUPLE LIST E2 NODES
####################
# turn each list of lists into a list of tuples,
# as tuples are hashable (lists are not) so we can convert the list of tuples into a set of tuples:
def get_e2_nodes_in_tuple_set():
    e2nodes_set = set()
    e2nodesidx_set = set()
    e2nodes_set_list = []
    e2nodesidx_set_lst = []
    conn = ric.conn_e2_nodes()
    for i in range(0, len(conn)):
        # TODO: need to fix cu_du_id in swig
        # cu_du_id = -1
        # if conn[i].id.cu_du_id:
        #     cu_du_id = conn[i].id.cu_du_id
        plmn = "PLMN_" + str(conn[i].id.plmn.mcc) + str(conn[i].id.plmn.mnc)
        nbid = "NBID_" + str(conn[i].id.nb_id.nb_id)
        info = {nbid,
                plmn,
                get_ngran_name(conn[i].id.type)}
        info_idx = {i,
                    nbid,
                    plmn,
                    get_ngran_name(conn[i].id.type)}
        # print(info)
        e2nodes_set_list.append(info)
        e2nodesidx_set_lst.append(info_idx)
    e2nodes_tuple_of_sets = tuple(e2nodes_set_list)
    e2nodes_idx_tuple_of_sets = tuple(e2nodesidx_set_lst)
    return e2nodes_tuple_of_sets, e2nodes_idx_tuple_of_sets


def clean_hndlr(id):
    key = gen_id_key(conn[idx].id)
    global mac_hndlr
    if key in mac_hndlr:
        del mac_hndlr[key]
    global rlc_hndlr
    if key in rlc_hndlr:
        del rlc_hndlr[key]
    global pdcp_hndlr
    if key in pdcp_hndlr:
        del pdcp_hndlr[key]
    global gtp_hndlr
    if key in gtp_hndlr:
        del gtp_hndlr[key]        
    global kpm_hndlr
    if key in kpm_hndlr:
        del kpm_hndlr[key]

####################
####  GENERAL
####################

ric.init(sys.argv)
start_http_server(8000)
cust_sm = ric.get_cust_sm_conf()
# for i in range(0, len(cust_sm)):
#     print(cust_sm[i].name, cust_sm[i].time)
oran_sm = ric.get_oran_sm_conf()

signal.signal(signal.SIGINT, sig_handler)

e2nodes = 0
e2nodes_set, e2nodesidx_set = get_e2_nodes_in_tuple_set()
# print("e2nodes")
# print(e2nodes_set)
while not e2nodes_set:
    print("No E2 node connects")
    time.sleep(1)

    temp_e2nodes_set, temp_e2nodes_idx_set = get_e2_nodes_in_tuple_set()

    if temp_e2nodes_set: # new - old
        # print("e2nodes_set ", e2nodes_set)
        # print("temp_e2nodes_set ", temp_e2nodes_set)
        print("Update connected E2 nodes")
        e2nodes_set = temp_e2nodes_set
        e2nodes_idx_set = temp_e2nodes_idx_set

assert(e2nodes_set)
print_e2_nodes()

conn = ric.conn_e2_nodes()
mac_hndlr = {}
rlc_hndlr = {}
pdcp_hndlr = {}
gtp_hndlr = {}
kpm_hndlr = {}
for i in range(0, len(conn)):
    send_subscription_req(conn[i], cust_sm, oran_sm)
    time.sleep(1)

while True:
    temp_e2nodes_set, temp_e2nodes_idx_set = get_e2_nodes_in_tuple_set()

    if not temp_e2nodes_set:
        print("No E2 node connects")
        e2nodes_set = set()

    # print("e2nodes_set ", e2nodes_set)
    # print("temp_e2nodes_set ", temp_e2nodes_set)

    # leave set
    leave_sets = set()
    for leave_set in e2nodes_set:
        if leave_set not in temp_e2nodes_set:
            leave_sets.add(tuple(leave_set))

    # new coming set
    new_sets = set()
    for new_set in temp_e2nodes_set:
        if new_set not in e2nodes_set:
            new_sets.add(tuple(new_set))

    if new_sets or leave_sets:
        if leave_sets:
            print("Left E2-Nodes: ", leave_sets)

        print("Update connected E2 nodes")
        e2nodes_set = temp_e2nodes_set
        e2nodes_idx_set = temp_e2nodes_idx_set
        e2nodes_len = len(e2nodes_set)
        print_e2_nodes()

        if new_sets:
            print("New E2-Nodes: ", new_sets)
            conn = ric.conn_e2_nodes()
            for ns in new_sets:
                for idx_set in e2nodes_idx_set:
                    if set(ns).issubset(set(idx_set)):
                        # print(f"ns {ns}, idx_set{idx_set}")
                        idx = -1
                        for value in idx_set:
                            if isinstance(value, int):
                                idx = value
                                break
                        if idx >= 0:
                            clean_hndlr(conn[idx].id)
                            send_subscription_req(conn[idx], cust_sm, oran_sm)
                        else:
                            print(f"Error: cannot find E2 node idx from the set")
                        break


    time.sleep(1)
