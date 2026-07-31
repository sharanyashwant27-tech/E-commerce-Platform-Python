import json
import urllib.parse
import urllib.request

data = urllib.parse.urlencode(
    {"username": "admin@shopsphere.local", "password": "Admin@12345"}
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8908/api/v1/login",
    data=data,
    method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
tok = json.loads(urllib.request.urlopen(req).read())["access_token"]
req2 = urllib.request.Request(
    "http://127.0.0.1:8908/api/v1/admin/analytics",
    headers={"Authorization": f"Bearer {tok}"},
)
body = json.loads(urllib.request.urlopen(req2).read())
keys = [
    "today_orders",
    "total_revenue",
    "pending_orders",
    "cancelled_orders",
    "low_stock_count",
    "top_selling_products",
    "recent_customers",
    "categories",
    "notifications",
]
print({k: body.get(k) for k in keys})

req3 = urllib.request.Request(
    "http://127.0.0.1:8908/admin", headers={"Cookie": f"access_token={tok}"}
)
html = urllib.request.urlopen(req3).read().decode()
for s in [
    "Today's Orders",
    "Sales Graph",
    "Revenue Graph",
    "Top Selling Products",
    "Recent Customers",
    "Product Categories",
    "Notifications",
    "Low Stock",
]:
    print(s, "OK" if s in html else "MISSING")
