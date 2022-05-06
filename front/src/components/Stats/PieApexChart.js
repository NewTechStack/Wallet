import React from "react"
import ReactApexChart from "react-apexcharts"

const PieApexChart = (props) => {
    const series = props.series || []
    const options = {
        labels: props.labels,
        colors: ["#34c38f","#f46a6a", "#556ee6", "#50a5f1", "#f1b44c"],
        legend: {
            show: true,
            position: "right",
            horizontalAlign: "center",
            verticalAlign: "middle",
            floating: false,
            fontSize: "14px",
            offsetX: 0,
            offsetY: -10,
        },
        responsive: [
            {
                breakpoint: 600,
                options: {
                    chart: {
                        height: 240,
                    },
                    legend: {
                        show: false,
                    },
                },
            },
        ],
        tooltip: {
            enabled: true,
            style: {
                fontSize: '16px',
                fontFamily:"Poppins,sans-serif"
            },
        }

    }

    return (
        <ReactApexChart options={options} series={series} type="pie" height="380" />
    )
}

export default PieApexChart
