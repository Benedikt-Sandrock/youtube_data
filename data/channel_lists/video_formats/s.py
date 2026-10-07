import pandas as pd

clist = ["UC5NOEUbkLheQcaaRldYW5GA",
         "UCACdxU3VrJIJc7ujxtHWs1w",
         "UCwyiPnNlT8UABRmGmU0T9jg",
         "UCeqKIgPQfNInOswGRWt48kQ",
         "UCMIgOXM2JEQ2Pv2d0_PVfcg",
         "UCZMsvbAhhRblVGXmEXW8TSA",
         "UC4zcMHyrT_xyWlgy5WGpFFQ",
         "UCSeil5V81-mEGB1-VNR7YEA",
         "UCcPcua2PF7hzik2TeOBx3uw",
         "UCMpW4tdyZUid2Ka9_FuDDhQ",]

alist = [
    "UC62IIFhchBWQxLPSyUatD-A", "UCJiRXf1Pb0ZkoPD7qcQIvlg", "UCyH9w3VhfZPdjH28VFeoHUA",
     "UC-qQ1TNcFK3DqD7jEK5D_jg", "UCq-b0dwW97YRZWgSCikWQRA", "UCnk0-FU1ybs9MpWg8g3yqMw",
     "UCsekpwdMv9PBCOftuuKncfw", "UCpV9LpCg4uwYCQZ3qoEn_YQ",
     "UCqZSdUJqd2T0oqr6BEA3ONw", "UCbanHTRuGv2Fi7flpO735yw", "UCiTKi7Ahf3E2yMGpmIxSvgw",
     "UCthYpKoujTMmDX75fGr5o8A", "UCiTJladOHCMkKndVBsn23VQ", "UCvOXPxj9VHHUQjGWENjpceg",
]

df = pd.DataFrame({"channel_id": alist})
df.to_csv("alt_kanaele.csv", index = False)