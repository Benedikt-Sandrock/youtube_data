ids = "UC4zcMHyrT_xyWlgy5WGpFFQ,UC5NOEUbkLheQcaaRldYW5GA,UC7n_Hml4hw5H4G-HP8QPeKw,UCCjkK_Qk9BUytDlAzz0iCZw,UCZMsvbAhhRblVGXmEXW8TSA,UCwyiPnNlT8UABRmGmU0T9jg,UCyQpfuhftLvrmjxgEzVH78Q"
ids = ids.split(",")
print(ids)
import pandas as pd
df = pd.DataFrame(ids, columns = ["channel_id"])
df.to_csv("missing_channels.csv", index = False)