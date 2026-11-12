import logging
from datetime import date
from ..models import Comunicacion
from . import sendgrid_service, twilio_service
from .configuracion import estado_proveedores, email_valido, telefono_valido

logger = logging.getLogger(__name__)
CANALES = {'Email': 'sendgrid', 'SMS': 'twilio_sms', 'WhatsApp': 'twilio_whatsapp', 'Llamada': 'twilio_voice'}


class DestinatarioInvalido(ValueError):
    """Excepción de dominio cuando el contacto del cliente no es válido para el canal solicitado."""


def registrar(db, cliente, canal, mensaje, estrategia_id=None):
    real = estado_proveedores()[CANALES[canal]]
    # La demo histórica admite clientes sin contacto. Solo el envío exige destinatario.
    if real:
        valido = email_valido(cliente.email) if canal == 'Email' else telefono_valido(cliente.telefono)
        if not valido:
            raise DestinatarioInvalido(
                'El cliente requiere un email válido.' if canal == 'Email'
                else 'El cliente requiere teléfono internacional válido (E.164).'
            )
    registro = Comunicacion(cliente_id=cliente.id, canal=canal, mensaje=mensaje, estrategia_id=estrategia_id,
        fecha_envio=date.today(), exitoso=False, modo='real' if real else 'simulado',
        estado='Pendiente' if real else 'Simulado',
        provider=('sendgrid' if canal == 'Email' else 'twilio') if real else None)
    db.add(registro)
    db.commit()  # Persistir intención antes de contactar al proveedor.
    if real:
        try:
            if canal == 'Email':
                identificador = sendgrid_service.enviar_email(cliente.email, 'Comunicación PluriOne', mensaje)
            else:
                identificador = twilio_service.enviar_mensaje(cliente.telefono, mensaje,
                    whatsapp=canal == 'WhatsApp', comunicacion_id=registro.id)
        except Exception:
            # Código fijo: nunca persistir str(exc), respuesta, URL, destinatario ni credenciales.
            db.refresh(registro, with_for_update=True)
            if registro.provider_status is None:
                registro.estado = 'Fallido'
                registro.error_tecnico = 'ProviderRequestFailed'
            logger.warning('Error %s al enviar %s: ProviderRequestFailed', registro.provider, canal)
        else:
            # Errores de persistencia deben propagarse como tales, no como fallos SDK.
            db.refresh(registro, with_for_update=True)
            registro.external_id = identificador
            if registro.provider_status is None:
                registro.exitoso = True
                registro.estado = 'Enviado'  # Aceptación, no entrega.
        db.commit()
    db.refresh(registro)
    return registro


def respuesta(registro):
    return {campo: getattr(registro, campo) for campo in
            ('id', 'cliente_id', 'canal', 'fecha_envio', 'mensaje', 'exitoso', 'modo', 'estado', 'provider')} | {
                'estrategia_id': getattr(registro, 'estrategia_id', None),
                'provider_status': getattr(registro, 'provider_status', None),
                'simulada': registro.modo == 'simulado'}
