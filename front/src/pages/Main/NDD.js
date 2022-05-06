import React, {useEffect} from "react";
import {Card, CardBody} from "reactstrap";
import DataTable from "react-data-table-component";
import {customTableStyle, paginationOptions, tableContextMessage} from "../../constants/defaultValues";
import IconButton from "@material-ui/core/IconButton";
import EditIcon from "@material-ui/icons/Edit";
import DeleteIcon from "@material-ui/icons/Delete";
import Lozenge from "@atlaskit/lozenge";


export default function NDD(props){

    const ndd_columns = [
        {
            name: 'Actions',
            cell: row => <div style={{justifyContent: "center"}}>
                <IconButton size="small" onClick={() => {

                }}>
                    <EditIcon fontSize="small" color="primary"/>
                </IconButton>
                <IconButton size="small" onClick={() => {

                }}>
                    <DeleteIcon fontSize="small" color="error"/>
                </IconButton>
            </div>
            ,
            grow: 0.1,
            center: true
        },
        {
            name: 'Nom de domaine',
            cell: row => <div>
                {row.name}
            </div>,
            sortable: true,
            grow: 0.3
        },
        {
            name: 'Date de création',
            cell: row => <div>
                {row.created_at}
            </div>,
            sortable: true,
            grow: 0.3
        },
        {
            name: 'Utilisateur',
            cell: row => <div>
                {row.user}
            </div>,
            sortable: true,
            grow: 0.3
        },
        {
            name: 'Status',
            cell: row => <div>
                {
                    row.status === "active" ?
                        <Lozenge appearance="success" isBold>
                            active
                        </Lozenge> :
                        row.status === "not-active" ?
                            <Lozenge appearance="removed" isBold>
                                desactivé
                            </Lozenge> :
                            <Lozenge appearance="moved" isBold>
                                en attente
                            </Lozenge>
                }
            </div>,
            sortable: true,
            grow: 0.3
        }
    ];

    const fake_ndd = [
        {
            id:"1",
            name:"amine.babba.com",
            created_at:"12/10/2021",
            user:"Babba Amine",
            status:"active"
        },
        {
            id:"2",
            name:"eliot.courtel.com",
            created_at:"02/07/2020",
            user:"Eliot Courtel",
            status:"not-active"
        },
        {
            id:"3",
            name:"jawher.zairi.fr",
            created_at:"17/05/2019",
            user:"Jawher Zairi",
            status:"wait"
        },
    ]

    useEffect(() => {
        props.setCurrentPage()
    }, []);

    return(
        <>
            <div className="container-fluid" style={{marginTop:60,marginLeft:15}}>
                <div className="row mb-4">
                    <div className="col-lg-12">
                        <Card>
                            <CardBody>
                                <div className="d-flex flex-wrap align-items-center mb-4">
                                    <h5 className="card-title me-2">Liste des NDD</h5>
                                </div>
                                <DataTable
                                    columns={ndd_columns}
                                    data={fake_ndd}
                                    defaultSortField={"name"}
                                    selectableRows={false}
                                    selectableRowsHighlight={true}
                                    pagination={true}
                                    paginationPerPage={10}
                                    paginationComponentOptions={paginationOptions}
                                    highlightOnHover={false}
                                    contextMessage={tableContextMessage}
                                    progressPending={!fake_ndd}
                                    progressComponent={<h6>Chargement...</h6>}
                                    noDataComponent="Il n'y a aucun nom de domaine  à afficher"
                                    noHeader={true}
                                    pointerOnHover={true}
                                    onRowClicked={(row, e) => {
                                    }}
                                    customStyles={customTableStyle}
                                />
                            </CardBody>
                        </Card>
                    </div>

                </div>
            </div>
        </>
    )
}
