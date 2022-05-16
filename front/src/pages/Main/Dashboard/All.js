import React, {useEffect} from "react";
import MuiBackdrop from "../../../components/Loading/MuiBackdrop";
import {Card, CardBody} from "reactstrap";
import {textTitleColor} from "../../../constants/defaultValues";
import Button from "@atlaskit/button";
import AddIcon from "@material-ui/icons/Add";
import WalletService from "../../../provider/walletService";
import {toast} from "react-toastify";
import polygon_icon from "../../../assets/icons/polygon.png"
import empty_icon from "../../../assets/icons/empty_icon2.png"
import wallet_icon from "../../../assets/icons/wallet_icon_1.png"
import InlineDialog from '@atlaskit/inline-dialog';
import FileCopyOutlinedIcon from '@material-ui/icons/FileCopyOutlined';
import SearchOutlinedIcon from '@material-ui/icons/SearchOutlined';
import Modal, {
    ModalBody,
    ModalFooter,
    ModalHeader,
    ModalTitle,
    ModalTransition,
} from '@atlaskit/modal-dialog';
import QRCode from "react-qr-code";
import PQueue from "p-queue";
import CircularProgress from '@material-ui/core/CircularProgress';
import DropdownMenu, {DropdownItem, DropdownItemGroup} from '@atlaskit/dropdown-menu';
import KeyboardBackspaceIcon from '@material-ui/icons/KeyboardBackspace';
import moment from "moment";

const chains = [
    {
        id: 0,
        title: "polygon - testnet"
    }
]

export default function All(props) {

    const [loading, setLoading] = React.useState(false);
    const [wallets, setWallets] = React.useState();
    const [selected_wallet, setSelected_wallet] = React.useState();
    const [contracts, setContracts] = React.useState();
    const [balance, setBalance] = React.useState();
    const [showContractDetails, setShowContractDetails] = React.useState(false);
    const [selected_contract, setSelected_contract] = React.useState();
    const [selected_contract_wallet_transactions, setSelected_contract_wallet_transactions] = React.useState();
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [openQrCodeModal, setOpenQrCodeModal] = React.useState(false);


    const [chain, setChain] = React.useState("polygon - testnet");

    useEffect(() => {
        console.log(props)
        get_wallets()
    }, []);

    const get_wallets = () => {

        WalletService.get_wallets(localStorage.getItem("usrtoken")).then(res => {
            console.log(res)
            if (res.status === 200 && res.succes === true) {
                if (res.data && res.data.wallets) {
                    if (res.data.wallets.length > 0) {

                        setWallets(res.data.wallets)
                        setSelected_wallet(res.data.wallets[res.data.wallets.length - 1])
                        setTimeout(() => {
                            getContracts(res.data.wallets[res.data.wallets.length - 1])
                        },250)
                    }
                }
            } else {
                console.log(res.error)
                toast.error(res.error, {
                    position: toast.POSITION.TOP_RIGHT
                });
            }

        }).catch(err => {
            console.log(err)
            toast.error("Une erreur est survenue", {
                position: toast.POSITION.TOP_RIGHT
            });
        })
    }

    const getContracts = (wallet) => {


        WalletService.getContracts(localStorage.getItem("usrtoken"), "polygon", "testnet", wallet.address).then(res => {
            console.log(res)
            if (res.status === 200 && res.succes === true) {
                let objArray = [];
                Object.keys(res.data).forEach(key => objArray.push({
                    id: key,
                    data: res.data[key]
                }));

                let queue = new PQueue({concurrency: 1});
                let calls = [];
                objArray.map(item => {
                    calls.push(() => getContractDetails(item.id).then(result => {
                        item.data.name = result.name
                        item.data.symbol = result.symbol
                        item.metadata = result.metadata
                    }))
                })
                queue.addAll(calls).then( async final => {
                    console.log(objArray)
                    setContracts(objArray)
                    if(props.history.location.hash && props.history.location.hash.trim() !== ""){
                        let contract_id = props.history.location.hash.substring(1)
                        console.log(contract_id)
                        let find_index = objArray.findIndex(x => x.id === contract_id)
                        if(find_index > -1){
                            let transactions = await getContractWalletTransactions(wallet.id,objArray[find_index].data.address)
                            console.log(transactions)
                            if(transactions && transactions !== "false"){
                                setSelected_contract_wallet_transactions(transactions)
                            }else{
                                setSelected_contract_wallet_transactions([])
                            }
                            setSelected_contract(objArray[find_index])
                            setShowContractDetails(true)
                        }
                    }
                }).catch(err => {
                    console.log(err)
                })

            } else {

            }
        }).catch(err => {
            console.log(err)
        })
    }


    const getContractDetails = (contract_id) => {
        return new Promise(resolve => {
            let data = {}
            WalletService.getContractData("polygon", "testnet", contract_id, localStorage.getItem("usrtoken")).then(r0 => {
                if (r0.data && Array.isArray(r0.data) && r0.data.length > 0 && r0.data[0].metadata) data.metadata = r0.data[0].metadata
                WalletService.getContractName("polygon", "testnet", contract_id, {kwargs: {}}, localStorage.getItem("usrtoken")).then(r1 => {
                    data.name = r1.data.result
                    WalletService.getContractSymbol("polygon", "testnet", contract_id, {kwargs: {}}, localStorage.getItem("usrtoken")).then(r2 => {
                        data.symbol = r2.data.result
                        resolve(data)
                    }).catch(err => {
                        resolve("false")
                    })
                }).catch(err => {
                    resolve("false")
                })
            }).catch(err => {
                resolve("false")
            })

        })
    }



    const getContractWalletTransactions = (wallet_id,contract_adr) => {

        return new Promise(resolve => {

            WalletService.getContractWalletTransactions("polygon","testnet",wallet_id,contract_adr,localStorage.getItem("usrtoken")).then( res => {
                if (res.status === 200 && res.succes === true) {
                    resolve(res.data.transaction || [])
                }else{
                    resolve("false")
                }
            }).catch( err => {
                console.log(err)
                resolve("false")
            })


        })
    }

    const onQrCodeDownload = () => {
        const svg = document.getElementById("QRCode");
        const svgData = new XMLSerializer().serializeToString(svg);
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        const img = new Image();
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            const pngFile = canvas.toDataURL("image/png");
            const downloadLink = document.createElement("a");
            downloadLink.download = "QRCode";
            downloadLink.href = `${pngFile}`;
            downloadLink.click();
        };
        img.src = `data:image/svg+xml;base64,${btoa(svgData)}`;
    };

    return (
        <>
            <MuiBackdrop open={loading}/>

            <div className="container-fluid" style={{marginTop: 60, marginLeft: 20, marginRight: 20}}>

                {
                    wallets && wallets.length > 0 && selected_wallet &&
                    <div className="row mb-3">
                        <div className="col-lg-12 mb-2">
                            <Card style={{backgroundColor: "#fff", border: "unset", marginRight: 30}}>
                                <CardBody>
                                    <div style={{display: "flex", justifyContent: "space-between", cursor: "pointer"}}>
                                        <div style={{alignSelf: "center"}}>
                                            <div style={{marginLeft: 5, alignSelf: "center"}}>
                                                <DropdownMenu
                                                    trigger={({triggerRef, ...props}) => (
                                                        <h4
                                                            {...props}
                                                            ref={triggerRef}
                                                        >Portefeuille: {selected_wallet.name}
                                                        </h4>
                                                    )}
                                                >
                                                    <DropdownItemGroup>
                                                        {
                                                            wallets.map((item, key) => (
                                                                <DropdownItem testId={key}
                                                                              isDisabled={true}
                                                                              onClick={() => {
                                                                                  console.log(item)
                                                                                  /*setContracts()
                                                                                  setSelected_wallet(item)
                                                                                  getContracts(item.address)*/
                                                                              }}
                                                                >
                                                                    {item.name}
                                                                </DropdownItem>
                                                            ))
                                                        }
                                                    </DropdownItemGroup>
                                                </DropdownMenu>
                                            </div>


                                        </div>

                                        <div>
                                            <div style={{display: "flex", cursor: "pointer"}}>
                                                <img alt={""} src={polygon_icon}
                                                     style={{height: 30, width: 30, alignSelf: "center"}}/>
                                                <div style={{marginLeft: 5, alignSelf: "center"}}>
                                                    <DropdownMenu
                                                        trigger={({triggerRef, ...props}) => (
                                                            <h4
                                                                {...props}
                                                                ref={triggerRef}
                                                            >Polygon - testnet
                                                            </h4>
                                                        )}
                                                    >
                                                        <DropdownItemGroup>
                                                            {
                                                                chains.map((item, key) => (
                                                                    <DropdownItem testId={item.id}
                                                                    >
                                                                        {item.title}
                                                                    </DropdownItem>
                                                                ))
                                                            }
                                                        </DropdownItemGroup>
                                                    </DropdownMenu>
                                                </div>

                                            </div>

                                        </div>
                                    </div>
                                </CardBody>
                            </Card>
                        </div>
                    </div>
                }

                {
                    wallets && wallets.length > 0 &&
                    showContractDetails === false ?

                        <div className="row mb-4">
                            <div className="col-lg-12 mb-2">
                                <Card style={{backgroundColor: "#fff", border: "unset", marginRight: 30}}>
                                    <CardBody>
                                        <h4>Mes tokens</h4>

                                        {
                                            !contracts ?
                                                <div align="center" style={{marginTop: 50}}>
                                                    <CircularProgress size={30}/>
                                                </div> :
                                                <div>
                                                    {
                                                        contracts.map((item, key) => (
                                                            <div key={key} style={{
                                                                padding: 15,
                                                                cursor: "pointer",
                                                                backgroundColor: "#f0f0f0",
                                                                borderRadius: 7.5,
                                                                marginBottom: 20
                                                            }}
                                                                 onClick={async () => {
                                                                     console.log(item)
                                                                     setLoading(true)
                                                                     let transactions = await getContractWalletTransactions(selected_wallet.id,item.data.address)
                                                                     console.log(transactions)
                                                                     if(transactions && transactions !== "false"){
                                                                         setSelected_contract_wallet_transactions(transactions)
                                                                     }else{
                                                                         setSelected_contract_wallet_transactions([])
                                                                     }
                                                                     setSelected_contract(item)
                                                                     setShowContractDetails(true)
                                                                     setLoading(false)
                                                                     props.history.push("/main/dashboard/all#"+item.id)
                                                                 }}
                                                            >
                                                                <div className="row mb-1">
                                                                    <div className="col-lg-8 mb-1">
                                                                        <div style={{display: "flex"}}>
                                                                            <div style={{alignSelf: "center"}}>
                                                                                <img alt={""}
                                                                                     src={(item.metadata && item.metadata.img) ? ("data:image/png;base64," + item.metadata.img) : empty_icon}
                                                                                     style={{
                                                                                         width: 40,
                                                                                         height: 40,
                                                                                         borderRadius: "50%"
                                                                                     }}/>
                                                                            </div>
                                                                            <div style={{
                                                                                alignSelf: "center",
                                                                                marginLeft: 10
                                                                            }}>
                                                                                <h5>{item.data.symbol}</h5>
                                                                                <p style={{marginTop: -10}}>{item.data.name}</p>
                                                                            </div>

                                                                        </div>
                                                                    </div>
                                                                    <div align="center" className="col-lg-4 mb-1"
                                                                         style={{alignSelf: "center"}}>
                                                                        <h5>{item.data.balance + " tokens"}</h5>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ))
                                                    }
                                                    {
                                                        contracts.length === 0 &&
                                                            <div align="center" style={{marginTop:50,padding:10,backgroundColor:"#f0f0f0",borderRadius:7.5}}>
                                                                <h5>Vous n'avez aucun token à afficher</h5>
                                                            </div>
                                                    }
                                                </div>
                                        }

                                    </CardBody>
                                </Card>
                            </div>
                        </div>

                        :

                        selected_contract &&
                        <div>
                            <div align="left">
                                <KeyboardBackspaceIcon style={{marginBottom:10,cursor:"pointer"}}
                                                       fontSize={"large"}
                                    onClick={ () => {
                                        setSelected_contract_wallet_transactions([])
                                        setShowContractDetails(false)
                                        setSelected_contract()
                                        props.history.push("/main/dashboard/all")
                                    }}
                                />
                            </div>
                            <div style={{
                                padding: 15,
                                backgroundColor: "#f0f0f0",
                                borderRadius: 7.5,
                                marginBottom: 20,
                                marginRight:30
                            }}
                            >

                                <div style={{marginTop:10}}>
                                    <div style={{display: "flex",justifyContent:"center"}}>
                                        <div style={{alignSelf: "center"}}>
                                            <img alt={""}
                                                 src={(selected_contract.metadata && selected_contract.metadata.img) ? ("data:image/png;base64," + selected_contract.metadata.img) : empty_icon}
                                                 style={{
                                                     width: 60,
                                                     height: 60,
                                                     borderRadius: "50%"
                                                 }}/>
                                        </div>
                                        <div style={{
                                            alignSelf: "center",
                                            marginLeft: 10
                                        }}>
                                            <h5>{selected_contract.data.symbol}</h5>
                                            <p style={{marginTop: -10}}>{selected_contract.data.name}</p>
                                        </div>
                                    </div>
                                    <div align="center" style={{marginTop:25}}>
                                        <h2>{selected_contract.data.balance + " tokens"}</h2>
                                        <p className={"detailTr"} style={{marginTop:-10}}
                                           onClick={() => {
                                               window.open("https://mumbai.polygonscan.com/token/" + selected_contract.data.address ,"_blank")
                                           }}
                                        >détails</p>
                                    </div>
                                    <div style={{marginTop:20,marginLeft:20}}>
                                        <h4>Description:</h4>
                                        <h6>
                                            {
                                                (selected_contract.metadata && selected_contract.metadata.desc) ? selected_contract.metadata.desc : "Pas de description"
                                            }
                                        </h6>
                                    </div>
                                    <div style={{marginTop:35,marginLeft:20}}>
                                        <h4>Transactions:</h4>
                                        <p className="detailTr"
                                           onClick={() => {
                                               window.open("https://mumbai.polygonscan.com/token/" + selected_contract.data.address + "?a=" +selected_wallet.address ,"_blank")
                                           }}
                                        >détails de toutes les transactions</p>
                                        {
                                            selected_contract_wallet_transactions && selected_contract_wallet_transactions.length > 0 ?
                                                <div style={{marginTop:25}}>
                                                    {
                                                        selected_contract_wallet_transactions.map((item,key) => (
                                                            <div key={key} className="row mt-1 mb-1">
                                                                <div className="col-lg-3">
                                                                    <h6>{"Le " + moment(item.date).format("DD MMMM YYYY")}</h6>
                                                                </div>
                                                                <div className="col-lg-4">
                                                                    <h6>
                                                                    {
                                                                        item.transaction.from === selected_wallet.address ?
                                                                            ("envoie de " + item.transaction.input_clear.amount + " tokens") :
                                                                            ("reception de " + item.transaction.input_clear.amount + " tokens")
                                                                    }
                                                                    </h6>
                                                                </div>
                                                                <div className="col-lg-5">
                                                                    {
                                                                        item.transaction.from === selected_wallet.address ?
                                                                            <div style={{display:"flex"}}>
                                                                                <h6>{"Portfeuille: " + selected_wallet.name + " -> "}</h6>
                                                                                <h6 className="truncateAddress" title={item.transaction.input_clear.recipient}>{item.transaction.input_clear.recipient}</h6>
                                                                            </div> :
                                                                            <div style={{display:"flex"}}>
                                                                                <h6 className="truncateAddress" title={item.transaction.from}>{item.transaction.from}</h6>
                                                                                <h6>{" -> " + "Portefeuille: " + selected_wallet.name }</h6>
                                                                            </div>
                                                                    }


                                                                </div>
                                                            </div>
                                                        ))
                                                    }

                                                </div> :
                                                <h6>Pas de transactions effectuées</h6>
                                        }

                                    </div>
                                </div>

                            </div>
                        </div>

                }


                {/*<div className="row mb-4">
                    <div className="col-lg-12 mb-2">
                        <Card>
                            <CardBody>
                                <div className="d-flex flex-wrap align-items-center mb-4" style={{justifyContent: "space-between"}}>
                                    <h4 className="card-title me-2" style={{color:textTitleColor}}>Portefeuille (Polygon)</h4>
                                </div>
                                <div style={{padding:10}}>
                                    <Card style={{boxShadow:"0 4px 10px 0 rgba(0,0,0,.25)"}}>
                                        <CardBody>
                                            <h5 style={{textAlign:"center",marginTop:-9}}>{wallet ? wallet.name : ""}</h5>
                                            <div style={{display:"flex",justifyContent:"center",marginTop:-10}}>
                                                <h5 style={{fontSize:"0.8rem",color:"grey",textAlign:"center",marginRight:3}}>
                                                    {wallet && (wallet.address || '')}
                                                </h5>

                                                {
                                                    wallet && wallet.address &&
                                                    <InlineDialog
                                                        placement="top"
                                                        onClose={() => {
                                                            setDialogOpen(false)
                                                        }}
                                                        content={(
                                                            <div>
                                                                <p>Copié</p>
                                                            </div>
                                                        )}
                                                        isOpen={dialogOpen}
                                                    >
                                                        <FileCopyOutlinedIcon fontSize="default"
                                                                              style={{cursor:"pointer",marginTop:-3}}
                                                                              onClick={() => {
                                                                                  navigator.clipboard.writeText(wallet.address)
                                                                                  setDialogOpen(!dialogOpen)
                                                                              }}
                                                        />
                                                    </InlineDialog>
                                                }

                                                {
                                                    wallet && wallet.address &&
                                                    <SearchOutlinedIcon fontSize="default"
                                                                        style={{cursor:"pointer",marginTop:-3}}
                                                                        onClick={() => {
                                                                            setOpenQrCodeModal(true)
                                                                        }}
                                                    />
                                                }

                                            </div>

                                            <hr style={{marginTop:-2}}/>
                                            <div style={{marginTop:-5,textAlign:"center"}}>
                                                <img alt="" src={polygon_icon} style={{width:30,height:30}}/>
                                                <h5 style={{marginTop:8}}>{balance}&nbsp;MATIC</h5>
                                            </div>
                                        </CardBody>
                                    </Card>
                                </div>
                            </CardBody>
                        </Card>
                    </div>
                </div>*/}

                {/*<div className="row mb-3">
                    <div className="col-lg-12 mb-2">
                        <Card>
                            <CardBody>
                                <div className="d-flex flex-wrap align-items-center mb-4" style={{justifyContent: "space-between"}}>
                                    <h4 className="card-title me-2" style={{color:textTitleColor}}>Mes tokens</h4>
                                </div>
                                <div style={{padding:10}}>
                                    <Card style={{boxShadow:"0 4px 10px 0 rgba(0,0,0,.25)"}}>
                                        <CardBody>
                                            {
                                                !contracts ?
                                                    <div align="center" style={{marginTop:15}}>
                                                        <CircularProgress size={20} />
                                                    </div> :

                                                    <div id="cardCollpase4" className="collapse pt-3 show">
                                                        <div className="table-responsive">
                                                            <table className="table table-centered table-borderless mb-0">
                                                                <thead style={{backgroundColor:textTitleColor,color:"#fff",fontWeight:"normal"}}>
                                                                <tr>
                                                                    <th>Nom</th>
                                                                    <th>Symbol</th>
                                                                    <th>Valeur</th>
                                                                    <th>Détails</th>
                                                                </tr>
                                                                </thead>
                                                                <tbody>
                                                                {
                                                                    (contracts).map( (item,key) => (
                                                                        <tr key={key}>
                                                                            <td>
                                                                                {item.data.name}
                                                                            </td>
                                                                            <td>
                                                                                <span className="badge bg-soft-danger text-danger p-1 font-weight-bold">{item.data.symbol}</span>
                                                                            </td>
                                                                            <td>
                                                                                <div style={{display:"flex"}}>
                                                                                    <h6 style={{width:30}}>{item.data.balance}</h6>
                                                                                    <h6>tokens</h6>
                                                                                </div>

                                                                            </td>
                                                                            <td>
                                                                                <SearchOutlinedIcon fontSize="default"
                                                                                                    style={{cursor:"pointer",marginLeft:15}}
                                                                                                    onClick={() => {
                                                                                                        window.open("https://mumbai.polygonscan.com/token/" + item.data.address + "?a=" +wallet.address ,"_blank")
                                                                                                    }}
                                                                                />
                                                                            </td>
                                                                        </tr>
                                                                    ))
                                                                }
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                            }

                                        </CardBody>
                                    </Card>
                                </div>
                            </CardBody>
                        </Card>
                    </div>
                </div>*/}
            </div>

            {/*<ModalTransition>
                {openQrCodeModal && (
                    <Modal onClose={() => {
                        setOpenQrCodeModal(false)
                    }} width="small">
                        <div align="center" style={{marginTop: 15, marginBottom: 10}}>
                            <h2>{wallet ? wallet.name : ""}</h2>
                        </div>
                        <ModalBody>
                            <div style={{textAlign: "center"}}>
                                {
                                    wallet.address &&
                                    <div>
                                        <QRCode id="QRCode" value={wallet.address} level="M" size={150}
                                                title={wallet.name}/>
                                        <br/>
                                        <Button appearance="link"
                                                onClick={() => {
                                                    onQrCodeDownload()
                                                }}
                                                style={{marginTop: 5}}
                                        >
                                            Télécharger
                                        </Button>
                                        <br/>
                                        <Button appearance="link"
                                                onClick={() => {
                                                    console.log(wallet.address)
                                                    window.open("https://mumbai.polygonscan.com/address/" + wallet.address + "#tokentxns", "_blank")
                                                }}
                                        >
                                            Voir sur polygonscan.com
                                        </Button>
                                    </div>

                                }
                            </div>
                        </ModalBody>
                        <ModalFooter>
                            <Button appearance="subtle">Skip</Button>
                            <Button appearance="primary" onClick={closeModal} autoFocus>
                                Get started
                            </Button>
                        </ModalFooter>
                    </Modal>
                )}
            </ModalTransition>*/}

        </>
    )


}
