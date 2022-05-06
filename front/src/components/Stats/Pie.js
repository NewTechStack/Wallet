import React, { Component } from "react"
import ReactEcharts from "echarts-for-react"

const colors = ["#02a499", "#f8b425", "#ec4561", "#38a4f8", "#3c4ccf"]

class Pie extends Component {
    getOption = () => {
        return {
            toolbox: {
                show: false,
            },
            tooltip: {
                trigger: "item",
                formatter: "{a} <br/>{b} : {c} ({d}%)",
            },
            legend: {
                orient: "vertical",
                left: "left",
                data: this.props.items.map((item) => {return item.name}),
                textStyle: {
                    color: ["#74788d"],
                },
            },
            color: this.props.colors || colors,
            series: [
                {
                    name: this.props.name,
                    type: "pie",
                    radius: "55%",
                    center: ["55%", "55%"],

                    data: this.props.items,
                    itemStyle: {
                        emphasis: {
                            shadowBlur: 10,
                            shadowOffsetX: 0,
                            shadowColor: "rgba(0, 0, 0, 0.5)",
                        },
                    },
                },
            ],
        }
    }
    render() {
        return (
            <React.Fragment>
                <ReactEcharts style={{ height: "350px" }} option={this.getOption()} />
            </React.Fragment>
        )
    }
}
export default Pie
