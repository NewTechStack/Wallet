import React from 'react';
import {Card, CardBody} from 'reactstrap';
import { VectorMap } from "react-jvectormap";
import "./jquery-jvectormap.scss";

const StatsByLocation = (props) => {
    const map = React.createRef(null);

    const mapData = {
        FR: 65,
        CH: 30,
        TN: 5
    };

    return (
        <React.Fragment>
            <Card>
                <CardBody>
                    <div className="d-flex flex-wrap align-items-center mb-4">
                        <h5 className="card-title me-2">Utilisateurs par emplacement</h5>
                    </div>

                    <div id="sales-by-locations" data-colors='["#5156be"]' style={{height: "250px"}}>
                        <div style={{width: "100%", height: 500}}>

                            <VectorMap
                                map={"world_mill"}
                                backgroundColor="transparent" // change it to ocean blue: #0077be
                                zoomOnScroll={false}
                                ref={map}
                                normalizeFunction='polynomial'
                                containerStyle={{
                                    width: "100%",
                                    height: "50%",
                                }}
                                containerClassName="map"
                                regionStyle={{
                                    initial: {
                                        fill: "#e4e4e4",
                                        "fill-opacity": 0.9,
                                        stroke: "none",
                                        "stroke-width": 0,
                                        "stroke-opacity": 0
                                    },
                                    hover: {
                                        "fill-opacity": 0.8,
                                        cursor: "pointer"
                                    },
                                    selected: {
                                        fill: "#2938bc" // color for the clicked country
                                    },
                                    selectedHover: {}
                                }}
                                regionsSelectable={false}
                                series={{
                                    regions: [
                                        {
                                            values: mapData, // this is the map data
                                            scale: ["#F5B041", "#27AE60","#2980B9"], // your color game's here
                                            normalizeFunction: "polynomial"
                                        }
                                    ]
                                }}
                                zoomMin={3}
                                focusOn={["FR"]}
                            />

                        </div>
                    </div>

                    <div className="px-2 py-2">
                        <p className="mb-1">France <span className="float-end">60%</span></p>
                        <div className="progress mt-2" style={{height: "6px"}}>
                            <div className="progress-bar progress-bar-striped" role="progressbar"
                                 style={{width: "65%",backgroundColor:"#2980B9"}} aria-valuenow="75" aria-valuemin="0" aria-valuemax="75">
                            </div>
                        </div>

                        <p className="mt-3 mb-1">Suisse <span className="float-end">30%</span></p>
                        <div className="progress mt-2" style={{height: "6px"}}>
                            <div className="progress-bar progress-bar-striped" role="progressbar"
                                 style={{width: "30%",backgroundColor:"#27AE60"}} aria-valuenow="55" aria-valuemin="0" aria-valuemax="55">
                            </div>
                        </div>

                        <p className="mt-3 mb-1">Tunisie <span className="float-end">10%</span></p>
                        <div className="progress mt-2" style={{height: "6px"}}>
                            <div className="progress-bar progress-bar-striped" role="progressbar"
                                 style={{width: "10%",backgroundColor:"#F5B041"}} aria-valuenow="85" aria-valuemin="0" aria-valuemax="85">
                            </div>
                        </div>
                    </div>
                </CardBody>
            </Card>
        </React.Fragment>
    );
};

export default StatsByLocation;
