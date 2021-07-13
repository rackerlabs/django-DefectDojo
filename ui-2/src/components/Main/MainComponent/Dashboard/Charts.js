import React from "react";
import { Doughnut, Line } from "react-chartjs-2";
function DonutChart() {
  return (
    <div>
      <Doughnut
        data={{
          labels: ["Critical", "High", "Medium", "Low", "Informational"],
          datasets: [
            {
              backgroundColor: [
                "#8c0000",
                "#f0ad4e",
                "#f0de28",
                "#337ab7",
                "#E0E0E0",
              ],
              data: [10, 20, 40, 20, 10],
            },
          ],
        }}
      />
    </div>
  );
}

function BarChart() {
  return (
    <Line
      data={{
        labels: ["Jan", "feb", "Mar", "app", "may"],
        datasets: [
          {
            label: "bah bahi",
            data: [3, 4, 5, 6, 7, 7],
          },
        ],
      }}
    />
  );
}
export default DonutChart;
export { BarChart };
