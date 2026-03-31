from pydantic import BaseModel


class OTPSend(BaseModel):
    user_id: str
    phone: str


class OTPVerify(BaseModel):
    user_id: str
    phone: str
    otp_code: str
