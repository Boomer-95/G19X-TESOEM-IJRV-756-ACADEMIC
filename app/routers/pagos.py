from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import main, models, auth
from ..database import get_db

router = APIRouter(tags=["pagos"])


class PagoNuevo(BaseModel):
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)


@router.post("/api/deudas/{deuda_id}/pagos", status_code=201)
def registrar_pago(deuda_id: int, datos: PagoNuevo, db: Session = Depends(get_db),
                   user: dict = Depends(auth.get_entra_user)):
    try:
        cliente_id = db.query(models.Deuda.cliente_id).filter_by(id=deuda_id).scalar()
        if cliente_id is None:
            raise HTTPException(404, "Deuda no encontrada")
        cliente = db.query(models.Cliente).filter_by(id=cliente_id).with_for_update().first()
        if not cliente:
            raise HTTPException(404, "Cliente no encontrado")
        deuda = db.query(models.Deuda).filter_by(id=deuda_id).populate_existing().with_for_update().one()
        saldo = Decimal(str(deuda.saldo_pendiente)).quantize(Decimal("0.01"))
        if deuda.estatus == "Pagada" or saldo <= 0:
            raise HTTPException(409, "La deuda ya está pagada.")
        if datos.monto > saldo:
            raise HTTPException(422, "El monto no puede superar el saldo pendiente.")
        if deuda.fecha_vencimiento is None:
            raise HTTPException(409, "La deuda no tiene fecha de vencimiento.")
        pago = models.Pago(cliente_id=cliente.id, deuda_id=deuda.id, monto=float(datos.monto),
            fecha_pago=date.today(), fecha_vencimiento=deuda.fecha_vencimiento,
            dias_atraso=(date.today() - deuda.fecha_vencimiento).days, se_recuperó=True)
        db.add(pago)
        deuda.saldo_pendiente = float(saldo - datos.monto)
        deuda.estatus = main.estado_deuda(deuda)
        db.flush()
        riesgo = main.recalcular_riesgo(db, cliente)
        db.commit()
        return {"pago": main.pago_dict(pago), "nuevo_saldo": deuda.saldo_pendiente,
                "saldo_cliente": main.resumen_cliente(cliente)["monto_pendiente"],
                "estatus": deuda.estatus, **riesgo}
    except Exception:
        db.rollback()
        raise
