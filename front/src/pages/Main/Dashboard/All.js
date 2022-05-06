import React,{useEffect} from "react";
import MuiBackdrop from "../../../components/Loading/MuiBackdrop";
import {Card, CardBody} from "reactstrap";
import {textTitleColor} from "../../../constants/defaultValues";
import Button from "@atlaskit/button";
import AddIcon from "@material-ui/icons/Add";
import WalletService from "../../../provider/walletService";
import {toast} from "react-toastify";
import polygon_icon from "../../../assets/icons/polygon.png"
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


export default function All(props) {

    const [loading, setLoading] = React.useState(false);
    const [wallet, setWallet] = React.useState();
    const [contracts, setContracts] = React.useState();
    const [balance, setBalance] = React.useState();
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [openQrCodeModal, setOpenQrCodeModal] = React.useState(false);

    useEffect(() => {
        get_wallets()
    }, []);

    const get_wallets = () => {
        WalletService.get_wallets(localStorage.getItem("usrtoken")).then( res => {
            console.log(res)
            if(res.status === 200 && res.succes === true){
                if(res.data && res.data.wallets){
                    if(res.data.wallets.length > 0){

                        getContracts(res.data.wallets[res.data.wallets.length - 1].address)
                        WalletService.get_wallet_balance(localStorage.getItem("usrtoken"),res.data.wallets[res.data.wallets.length - 1].id).then( balanceRes => {
                            console.log(balanceRes)
                            if(balanceRes.status === 200 && balanceRes.succes === true){
                                setLoading(false)
                                setWallet(res.data.wallets[res.data.wallets.length - 1])
                                setBalance(balanceRes.data.data === 0 ? 0 : balanceRes.data.data / 1000000000000000000 )
                            }else{
                                console.log(balanceRes.error)
                                toast.error(balanceRes.error, {
                                    position: toast.POSITION.TOP_RIGHT
                                });
                            }
                        }).catch( err => {
                            console.log(err)
                        })
                    }
                }
            }else{
                console.log(res.error)
                toast.error(res.error, {
                    position: toast.POSITION.TOP_RIGHT
                });
            }

        }).catch( err => {
            console.log(err)
            toast.error("Une erreur est survenue", {
                position: toast.POSITION.TOP_RIGHT
            });
        })
    }

    const getContracts = (wallet_adrs) => {
        WalletService.getContracts(wallet_adrs).then( res => {

            if(res.status === 200 && res.succes === true){
                let objArray = [];
                Object.keys(res.data).forEach(key => objArray.push({
                    id: key,
                    data: res.data[key]
                }));

                let queue = new PQueue({concurrency: 1});
                let calls = [];
                objArray.map( item => {
                    calls.push(
                        () => WalletService.getContractName(item.id,{kwargs:{}},localStorage.getItem("usrtoken")).then( r1 => {
                            item.data.name = r1.data.result
                            WalletService.getContractSymbol(item.id,{kwargs:{}},localStorage.getItem("usrtoken")).then( r2 => {
                                item.data.symbol = r2.data.result
                            })
                        })
                    )
                })
                queue.addAll(calls).then( final => {
                    setContracts(objArray)
                    console.log(objArray)

                }).catch(err => {
                    console.log(err)
                })

            }else{

            }
        }).catch( err => {
            console.log(err)
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

            <div className="container-fluid" style={{marginTop: 60, marginLeft: 15}}>
                <div className="row mb-4">
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
                </div>

                <div className="row mb-3">
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
                </div>
            </div>

            <ModalTransition>
                {openQrCodeModal && (
                    <Modal onClose={() => {setOpenQrCodeModal(false)}} width="small">
                        <div align="center" style={{marginTop:15,marginBottom:10}}>
                            <h2>{wallet ? wallet.name : ""}</h2>
                        </div>
                        <ModalBody>
                            <div style={{textAlign:"center"}}>
                                {
                                    wallet.address &&
                                        <div>
                                            <QRCode id="QRCode" value={wallet.address} level="M" size={150} title={wallet.name}/>
                                            <br/>
                                            <Button appearance="link"
                                                    onClick={() => {
                                                        onQrCodeDownload()
                                                    }}
                                                    style={{marginTop:5}}
                                            >
                                                Télécharger
                                            </Button>
                                            <br/>
                                            <Button appearance="link"
                                                    onClick={() => {
                                                        console.log(wallet.address)
                                                        window.open("https://mumbai.polygonscan.com/address/" + wallet.address + "#tokentxns","_blank")
                                                    }}
                                            >
                                                Voir sur polygonscan.com
                                            </Button>
                                        </div>

                                }
                            </div>
                        </ModalBody>
                        {/*<ModalFooter>
                            <Button appearance="subtle">Skip</Button>
                            <Button appearance="primary" onClick={closeModal} autoFocus>
                                Get started
                            </Button>
                        </ModalFooter>*/}
                    </Modal>
                )}
            </ModalTransition>

        </>
    )


}
