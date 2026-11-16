
import pandas as pd
import matplotlib.pyplot as plt

data = {
    "Route": ["Coimbatore-Salem", "Coimbatore-Erode",
              "Coimbatore-Chennai", "Salem-Erode"],
    "Passengers": [120, 85, 150, 65]
}

df = pd.DataFrame(data)

plt.bar(df["Route"], df["Passengers"])
plt.title("Passenger Count by Route")
plt.xlabel("Bus Routes")
plt.ylabel("Number of Passengers")
plt.xticks(rotation=20)
plt.tight_layout()
plt.show()

import pandas as pd
import matplotlib.pyplot as plt

data = {
    "Month": ["January", "February", "March",
              "April", "May", "June"],
    "Passengers": [100, 150, 130, 180, 220, 250]
}

df = pd.DataFrame(data)

plt.plot(df["Month"], df["Passengers"],
         marker="o", linestyle="-")

plt.title("Monthly Passenger Travel Analysis")
plt.xlabel("Month")
plt.ylabel("Number of Passengers")
plt.grid(True)
plt.tight_layout()
plt.show()
